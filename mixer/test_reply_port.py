#!/usr/bin/env python3
"""Socket-level tests for optional per-request OSC reply ports."""
import math
import os
import socket
import subprocess
import sys
import time

from mixerctl import packet, parse_packet

ROOT = os.path.dirname(os.path.dirname(__file__))
CONFIG = os.path.join(ROOT, "payload", "config", "mixer.conf")


def free_udp_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def receive(sock):
    return parse_packet(sock.recv(65535))


def expect(sock, path):
    reply = receive(sock)
    assert reply[0] == path, reply
    return reply


listen = free_udp_port()
server = subprocess.Popen([
    sys.executable, os.path.join(ROOT, "mixer", "mixerctl.py"),
    "serve", CONFIG, "--listen", str(listen), "--no-node",
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
source = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
source.settimeout(1)
explicit = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
explicit.bind(("127.0.0.1", 0))
explicit.settimeout(1)


def request(data, destination=source):
    destination.sendto(data, ("127.0.0.1", listen))


try:
    time.sleep(0.15)

    # Legacy requests still reply to the request socket's ephemeral source port.
    request(packet("/mixer/get", ",s", ["master"]))
    assert receive(source)[0] == "/mixer/state"
    request(packet("/mixer/set", ",sf", ["master", 0.5]))
    assert receive(source)[0] == "/mixer/ok"
    request(packet("/mixer/meters", ","))
    assert len(expect(source, "/mixer/meters")[2]) == 80

    # Explicit integer and whole-valued float ports are request-local and keep
    # the sender IP. Each request is sent from a different source socket to
    # ensure there is no persistent client registration.
    explicit_port = explicit.getsockname()[1]
    request(packet("/mixer/get", ",si", ["master", explicit_port]))
    assert expect(explicit, "/mixer/state")[2][0] == "master"
    request(packet("/mixer/set", ",sfi", ["master", 0.25, explicit_port]))
    assert expect(explicit, "/mixer/ok")[2] == ["master"]
    request(packet("/mixer/meters", ",i", [explicit_port]))
    assert len(expect(explicit, "/mixer/meters")[2]) == 80

    float_port = float(explicit_port)
    request(packet("/mixer/get", ",sf", ["master", float_port]))
    assert expect(explicit, "/mixer/state")[2][0] == "master"
    request(packet("/mixer/set", ",sff", ["master", 0.5, float_port]))
    assert expect(explicit, "/mixer/ok")[2] == ["master"]
    request(packet("/mixer/meters", ",f", [float_port]))
    assert len(expect(explicit, "/mixer/meters")[2]) == 80

    # Invalid reply ports are rejected at the original source and never reach
    # the state mutation path. The decoder supplies integer, float, and string
    # OSC values for these cases.
    invalid_ports = [
        (",si", ["master", 0]),
        (",sf", ["master", -1.0]),
        (",sf", ["master", 65536.0]),
        (",sf", ["master", 10111.5]),
        (",sf", ["master", float("nan")]),
        (",sf", ["master", float("inf")]),
        (",ss", ["master", "10111"]),
    ]
    for types, values in invalid_ports:
        request(packet("/mixer/get", types, values))
        assert expect(source, "/mixer/error")[0] == "/mixer/error"
        explicit.settimeout(0.05)
        try:
            explicit.recv(65535)
            raise AssertionError(("invalid port reached explicit socket", types, values))
        except socket.timeout:
            pass
        finally:
            explicit.settimeout(1)

    request(packet("/mixer/meters", ",s", ["10111"]))
    expect(source, "/mixer/error")

    request(packet("/mixer/get", ",s", ["master"]))
    before = expect(source, "/mixer/state")[2][1]
    request(packet("/mixer/set", ",sfi", ["master", 0.75, 0]))
    expect(source, "/mixer/error")
    request(packet("/mixer/get", ",s", ["master"]))
    after = expect(source, "/mixer/state")[2][1]
    assert math.isclose(before, after), (before, after)

    # Arity remains strict for all three request forms.
    for data in (
        packet("/mixer/get", ",sii", ["master", 10111, 10112]),
        packet("/mixer/set", ",sfs", ["master", 0.5, "extra"]),
        packet("/mixer/meters", ",ii", [10111, 10112]),
    ):
        request(data)
        expect(source, "/mixer/error")
    print("PASS legacy and explicit OSC reply-port routing, strict validation, and non-mutation")
finally:
    source.close()
    explicit.close()
    server.terminate()
    server.wait(timeout=2)

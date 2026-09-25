#!/usr/bin/env python3
import os, socket, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(__file__))
from mixerctl import BUS_RANGES, GROUPS, controls, packet, parse_packet, read_config

config = "/workspace/payload/config/mixer.conf"
values, channels = read_config(config)
assert list(BUS_RANGES.values()) == [(26,52),(52,60),(60,76),(76,108),(0,26)]
assert len({tuple(x) for x in BUS_RANGES.values()}) == 5
state = dict(controls(values, channels))
assert state["trim0"] == 1 and state["mute0"] == 0 and state["polarity0"] == 1
assert state["hpf0"] == 0 and state["group0_0"] == 1 and state["group0_1"] == 0
assert state["groupLevel0"] == 1 and state["master"] == 1 and state["bypass"] == 0
print("neutral controls, groups, mute, polarity, HPF-disabled, levels, bypass: OK")

proc = subprocess.Popen([sys.executable, os.path.join(os.path.dirname(__file__), "mixerctl.py"),
                         "serve", config, "--port", "57118", "--listen", "57121", "--no-node"],
                        stdout=None, stderr=None)
try:
    time.sleep(0.3)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.settimeout(2)
    sock.sendto(packet("/mixer/get", ",s", ["master"]), ("127.0.0.1", 57121))
    assert parse_packet(sock.recv(4096))[0] == "/mixer/state"
    sock.sendto(packet("/mixer/set", ",sf", ["master", 0.5]), ("127.0.0.1", 57121))
    assert parse_packet(sock.recv(4096))[0] == "/mixer/ok"
    sock.sendto(packet("/mixer/set", ",sf", ["master", float("nan")]), ("127.0.0.1", 57121))
    assert parse_packet(sock.recv(4096))[0] == "/mixer/error"
    print("OSC getter, setter, invalid NaN rejection: OK")
finally:
    proc.terminate(); proc.wait(timeout=2)

# Real quad flow: run the reusable graph in quad mode and observe actual
# post-master meters. The fixture broadens constraints only for exhaustive
# corner coverage; production config retains the musical envelopes.
scene=open(config, encoding="utf-8").read().replace("routing.mode=direct", "routing.mode=quad")
import re
for name in GROUPS:
    scene=re.sub(rf"group\.{name}\.x_min=.*", f"group.{name}.x_min=0", scene)
    scene=re.sub(rf"group\.{name}\.x_max=.*", f"group.{name}.x_max=1", scene)
    scene=re.sub(rf"group\.{name}\.y_min=.*", f"group.{name}.y_min=0", scene)
    scene=re.sub(rf"group\.{name}\.y_max=.*", f"group.{name}.y_max=1", scene)
    scene=re.sub(rf"group\.{name}\.width_min=.*", f"group.{name}.width_min=0", scene)
    scene=re.sub(rf"group\.{name}\.width_max=.*", f"group.{name}.width_max=1", scene)
scene=scene.replace("channel.9.group=music_a", "channel.9.group=music_b")
with tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False) as fixture:
    fixture.write(scene); quad_config=fixture.name
quad_values, quad_channels=read_config(quad_config)
quad_proc=subprocess.Popen([sys.executable, os.path.join(os.path.dirname(__file__),"mixerctl.py"),"serve",quad_config,"--port","57118","--listen","57121"])
quad_sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); quad_sock.settimeout(2); time.sleep(.6)
quad_sock.sendto(packet("/g_queryTree", ",ii", [0, 1]), ("127.0.0.1", 57118))
tree_packet = quad_sock.recv(65535)
tree = parse_packet(tree_packet)
print("g_queryTree:", tree)
def quad_meters():
    time.sleep(.15)
    quad_sock.sendto(packet("/mixer/meters",","),("127.0.0.1",57121))
    while True:
        message=parse_packet(quad_sock.recv(65535))
        if message[0]=="/mixer/meters":
            result=[float(x) for x in message[2]]
            return result
def qset(key,value):
    quad_sock.sendto(packet("/mixer/set",",sf",[key,value]),("127.0.0.1",57121)); assert parse_packet(quad_sock.recv(65535))[0]=="/mixer/ok"
def qnode(g,x,y):
    quad_sock.sendto(packet("/n_set",",isfsfsf",[4000+g,"x",x,"y",y,"width",0]),("127.0.0.1",57118))
def qinject(bus,node):
    quad_sock.sendto(packet("/s_new",",siiisisfsfsi",["sc_adat_scan",node,0,0,"output",bus,"freq",440.0,"level",-12.0,"gate",1]),("127.0.0.1",57118)); time.sleep(.05)
    quad_sock.settimeout(.05)
    try:
        while True:
            reply=parse_packet(quad_sock.recv(65535))
            if reply[0] in ("/fail", "/n_go"): print("inject-reply", reply)
    except socket.timeout: pass
    finally: quad_sock.settimeout(2)
    # Allow the authoritative DSP smoothing and one meter packet to settle.
    time.sleep(.45)
def qstop(node):
    token = 9000 + node
    quad_sock.sendto(packet("/n_free",",i",[node]),("127.0.0.1",57118))
    quad_sock.sendto(packet("/sync",",i",[token]),("127.0.0.1",57118))
    deadline=time.time()+1.0
    while time.time() < deadline:
        try:
            reply=parse_packet(quad_sock.recv(65535))
            if reply[0] == "/synced": break
        except socket.timeout: break
    time.sleep(.20)
    quad_sock.sendto(packet("/n_query",",i",[node]),("127.0.0.1",57118))
    quad_sock.settimeout(1)
    try:
        reply=parse_packet(quad_sock.recv(65535))
        assert reply[0] == "/fail", ("scan node still exists", node, reply)
    finally:
        quad_sock.settimeout(2)
def wait_quiet(label, threshold=0.01):
    deadline=time.time()+3.0; quiet=0; samples=[]
    while time.time() < deadline:
        values_now=quad_meters(); peaks=values_now[48:64]; rms=values_now[64:80]
        samples.append((peaks[:4], rms[:4]))
        if max(peaks+rms) < threshold:
            quiet += 1
            if quiet >= 4: return
        else: quiet=0
    raise AssertionError(("quiescence timeout", label, samples[-6:]))
try:
    source_by_group={GROUPS.index(row["group"]):26+int(row["input"])-1 for row in quad_channels}
    assert set(source_by_group)==set(range(8))
    qinject(52,7000)
    time.sleep(.2)
    print("private bus 52 writer/reader probe complete")
    qstop(7000)
    wait_quiet("after private bus 52 probe")
    corners=[(-1,1,0), (1,1,1), (-1,-1,2), (1,-1,3)]
    for g in range(8):
        for x,y,output in corners:
            node=5000+g*4+output; qnode(g,x,y); qinject(source_by_group[g],node); values_now=quad_meters(); peaks=values_now[48:64]
            assert peaks[output] > 0.01, (g, output, "input", values_now[:16], "groups", values_now[32:48], "outputs", peaks)
            assert all(v < 0.01 for i,v in enumerate(peaks) if i != output), (g, output, peaks)
            qstop(node)
    qnode(0,0,0); qinject(source_by_group[0],5800); centre=quad_meters()[48:52]; assert max(centre)-min(centre) < 0.08, centre; qstop(5800)
    qnode(0,-1,1); qnode(1,-1,1); qinject(source_by_group[0],5900); qinject(source_by_group[1],5901); summed=quad_meters()[48:52]; assert summed[0] > 0.02 and max(summed[1:]) < 0.01, summed; qstop(5900); qstop(5901)
    qset("quadSmoothingMs",200); qnode(0,-1,1); qinject(source_by_group[0],6000); before=quad_meters()[48:52]; qset("group0PosX",1); time.sleep(.03); early=quad_meters()[48:52]; time.sleep(.25); late=quad_meters()[48:52]; assert early[0] > late[0] and late[1] > early[1], (before,early,late); qstop(6000)
    print("real scsynth quad flow: 8 groups x 4 corners, centre, transposed two-group sum, meter identity and configurable smoothing: OK")
finally:
    quad_proc.terminate(); quad_proc.wait(timeout=2); quad_sock.close(); os.unlink(quad_config)

# Actual sample-flow test: the scan SynthDef writes simulated hardware input
# buses 26..41. The mixer must read those buses and emit only output buses 0..15.
proc = subprocess.Popen([sys.executable, os.path.join(os.path.dirname(__file__), "mixerctl.py"),
                         "serve", config, "--port", "57118", "--listen", "57121"],
                        stdout=None, stderr=None)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.settimeout(2)
time.sleep(0.5)
def meters():
    sock.sendto(packet("/mixer/meters", ","), ("127.0.0.1", 57121))
    return parse_packet(sock.recv(4096))[2]
def inject(input_bus):
    sock.sendto(packet("/s_new", ",siiisisfsfsi",
                       ["sc_adat_scan", 3100, 0, 0, "output", input_bus,
                        "freq", 440.0, "level", -30.0, "gate", 1]),
                ("127.0.0.1", 57118))
    time.sleep(0.6)
try:
    for channel in (1, 9, 16):
        values = meters()
        assert max(float(x) for x in values) < 0.01
        inject(26 + channel - 1)
        values = [float(x) for x in meters()]
        input_peaks, group_peaks, output_peaks = values[:16], values[32:40], values[48:64]
        assert input_peaks[channel - 1] > 0.01
        assert output_peaks[channel - 1] > 0.01
        assert all(x < 0.01 for i,x in enumerate(input_peaks) if i != channel - 1)
        assert all(x < 0.01 for i,x in enumerate(output_peaks) if i != channel - 1)
        expected_group = GROUPS.index(channels[channel - 1]["group"])
        assert group_peaks[expected_group] > 0.01, (channel, input_peaks, group_peaks, output_peaks)
        assert all(x < 0.01 for i,x in enumerate(group_peaks) if i != expected_group)
        sock.sendto(packet("/n_set", ",isi", [3100, "gate", 0]), ("127.0.0.1", 57118))
        time.sleep(0.4)
    inject(42)  # physical channel 17: outside the active 16-channel window
    values = [float(x) for x in meters()]
    assert max(values[:16] + values[48:64]) < 0.01
    print("sample flow buses 26->0, 34->8, 41->15; meters and channels 17..26: OK")
finally:
    proc.terminate(); proc.wait(timeout=2)

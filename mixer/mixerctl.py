#!/usr/bin/env python3
"""Small deterministic OSC/config controller for the transparent SC mixer."""
import argparse, math, os, signal, socket, struct, sys, time

GROUPS = ("drums", "bass", "instruments", "vocals", "fx_returns")
FIELDS = ("name", "input", "output", "group", "trim_db", "mute", "polarity", "hpf", "hpf_hz")
METER_WIDTH = 16 + 16 + 5 + 5 + 16 + 16

def osc_string(value):
    raw = value.encode() + b"\0"; return raw + b"\0" * ((4 - len(raw) % 4) % 4)
def packet(path, types, values=()):
    out = osc_string(path) + osc_string(types)
    for typ, value in zip(types[1:], values):
        if typ == "i": out += struct.pack(">i", int(value))
        elif typ == "f": out += struct.pack(">f", float(value))
        elif typ == "s": out += osc_string(str(value))
        else: raise ValueError("unsupported OSC type")
    return out
def osc_read(data, pos=0):
    end = data.index(b"\0", pos); text = data[pos:end].decode(); return text, (end + 4) & ~3
def parse_packet(data):
    path, pos = osc_read(data); types, pos = osc_read(data, pos); values=[]
    for typ in types[1:]:
        if typ == "i": values.append(struct.unpack(">i", data[pos:pos+4])[0]); pos += 4
        elif typ == "f": values.append(struct.unpack(">f", data[pos:pos+4])[0]); pos += 4
        elif typ == "s": value, pos = osc_read(data, pos); values.append(value)
        else: break
    return path, types, values
def finite(value, label):
    number=float(value)
    if not math.isfinite(number): raise ValueError(f"{label} must be finite")
    return number
def dbamp(db): return max(0.0001, min(2.0, 10.0 ** (finite(db, "gain") / 20.0)))
def as_bool(value): return int(str(value).lower() in ("1", "true", "yes", "on"))
def read_config(path):
    values = {}
    with open(path, encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            line=line.strip()
            if not line or line.startswith("#"): continue
            if "=" not in line: raise ValueError(f"line {line_no}: expected key=value")
            key, value = line.split("=", 1); values[key.strip()] = value.strip()
    if values.get("version") != "1": raise ValueError("version must be 1")
    channels = int(values.get("channels", "0")); capacity = int(values.get("max_channels", "24"))
    if channels != 16 or channels > capacity or capacity != 24: raise ValueError("mixer must be 16 active / 24 capacity")
    for name in GROUPS:
        finite(values[f"group.{name}.level_db"], f"group.{name}.level_db")
    finite(values["master.level_db"], "master.level_db"); as_bool(values["bypass"])
    channels_out=[]; seen_inputs=set(); seen_outputs=set()
    for ch in range(1, channels + 1):
        prefix=f"channel.{ch}."; row={}
        for field in FIELDS:
            key=prefix+field
            if key not in values: raise ValueError(f"missing {key}")
            row[field]=values[key]
        inp=int(row["input"]); out=int(row["output"])
        if not 1 <= inp <= 16 or not 1 <= out <= 16: raise ValueError("physical mixer mapping must stay in channels 1..16")
        if inp in seen_inputs or out in seen_outputs: raise ValueError("input/output mapping must be one-to-one")
        if inp != out: raise ValueError("this milestone only permits verified one-to-one input=output mapping")
        seen_inputs.add(inp); seen_outputs.add(out)
        if row["group"] not in GROUPS: raise ValueError(f"invalid group for channel {ch}")
        trim=finite(row["trim_db"], f"channel.{ch}.trim_db"); hpf_hz=finite(row["hpf_hz"], f"channel.{ch}.hpf_hz")
        if not -60 <= trim <= 12: raise ValueError("trim must be -60..12 dB")
        if not 20 <= hpf_hz <= 20000: raise ValueError("HPF frequency must be 20..20000 Hz")
        as_bool(row["mute"]); as_bool(row["hpf"])
        if int(row["polarity"]) not in (-1, 1): raise ValueError("polarity must be -1 or 1")
        channels_out.append(row)
    if seen_inputs != set(range(1,17)) or seen_outputs != set(range(1,17)): raise ValueError("mapping must cover all 16 channels")
    return values, channels_out
def controls(values, channels):
    result=[]
    for i,row in enumerate(channels):
        result += [(f"trim{i}", dbamp(row["trim_db"])), (f"mute{i}", as_bool(row["mute"])), (f"polarity{i}", int(row["polarity"])), (f"hpf{i}", as_bool(row["hpf"])), (f"hpfHz{i}", float(row["hpf_hz"]))]
        group=GROUPS.index(row["group"])
        result += [(f"group{i}_{g}", int(g == group)) for g in range(5)]
    for g,name in enumerate(GROUPS): result.append((f"groupLevel{g}", dbamp(values[f"group.{name}.level_db"])))
    result.append(("master", dbamp(values["master.level_db"]))); result.append(("bypass", as_bool(values["bypass"])))
    return result
def send(sock, port, data): sock.sendto(data, ("127.0.0.1", port))
def send_to(sock, address, data): sock.sendto(data, address)
def db(value): return -120.0 if value <= 1e-9 else 20.0 * math.log10(min(1.0, max(1e-9, value)))
def start_node(sock, port, controls_list):
    args=["sc_adat_mixer", 3000, 0, 0]; types=",siii"; vals=args
    for name,value in controls_list: types += "sf"; vals += [name, value]
    sock.settimeout(0.25)
    for _ in range(20):
        send(sock, port, packet("/notify", ",i", [1])); send(sock, port, packet("/n_free", ",i", [3000])); send(sock, port, packet("/s_new", types, vals))
        deadline=time.time() + 0.25
        while time.time() < deadline:
            try: path, _, _ = parse_packet(sock.recv(65535))
            except (socket.timeout, ValueError, IndexError): break
            if path == "/n_go": sock.settimeout(None); return
            if path == "/fail": break
        time.sleep(0.1)
    sock.settimeout(None)
    raise RuntimeError("scsynth did not acknowledge mixer node")
def apply(config, port=57110):
    values, channels=read_config(config); sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); start_node(sock, port, controls(values, channels)); time.sleep(.15); return values, channels
def serve(config, listen=57120, sc_port=57110, start=True):
    values, channels=read_config(config); sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.bind(("0.0.0.0", listen)); initial=controls(values, channels); state=dict(initial); meter_values=[0.0] * METER_WIDTH
    if start: start_node(sock, sc_port, initial)
    def shutdown(_signum, _frame):
        try:
            send(sock, sc_port, packet("/n_set", ",isf", [3000, "master", 0.0])); time.sleep(0.06)
            send(sock, sc_port, packet("/n_free", ",i", [3000]))
        finally:
            raise SystemExit(0)
    signal.signal(signal.SIGTERM, shutdown); signal.signal(signal.SIGINT, shutdown)
    meters=0
    while True:
        data, address=sock.recvfrom(65535); path, types, vals=parse_packet(data)
        if path == "/mixer/meter":
            numeric=[float(x) for x in vals if isinstance(x, (int, float)) and math.isfinite(float(x))]
            if len(numeric) >= METER_WIDTH: meter_values=numeric[-METER_WIDTH:]
            meters += 1
        elif path == "/mixer/meters":
            send_to(sock, address, packet("/mixer/meters", "," + "f" * METER_WIDTH, meter_values))
        elif path == "/mixer/set" and len(vals) == 2:
            key, value=vals; allowed={name for name,_ in controls(values, channels)}
            if key not in allowed:
                send_to(sock, address, packet("/mixer/error", ",s", ["invalid parameter"])); continue
            try: numeric=float(value)
            except (TypeError, ValueError): send_to(sock, address, packet("/mixer/error", ",s", ["value is not numeric"])); continue
            if not math.isfinite(numeric): send_to(sock, address, packet("/mixer/error", ",s", ["value must be finite"])); continue
            state[key]=numeric; send(sock, sc_port, packet("/n_set", ",isf", [3000, key, numeric])); send_to(sock, address, packet("/mixer/ok", ",s", [key]))
        elif path == "/mixer/get":
            key=str(vals[0]) if vals else "master"
            if key not in state: send_to(sock, address, packet("/mixer/error", ",s", ["invalid parameter"]))
            else: send_to(sock, address, packet("/mixer/state", ",sf", [key, state[key]]))
def get_meters(port=57120):
    sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.settimeout(2); send(sock, port, packet("/mixer/meters", ","))
    path, _, values=parse_packet(sock.recv(65535))
    if path != "/mixer/meters" or len(values) != METER_WIDTH: raise RuntimeError("meter stream unavailable")
    return [float(x) for x in values]
def print_meters(port=57120):
    values=get_meters(port)
    print("inputs  peak/rms dBFS")
    for i in range(16): print(f"I{i+1:02d} {db(values[i]):7.1f}/{db(values[16+i]):7.1f}", end="  " if i % 2 == 0 else "\n")
    print("groups  peak/rms dBFS")
    for i,name in enumerate(GROUPS): print(f"{name:<11} {db(values[32+i]):7.1f}/{db(values[37+i]):7.1f}")
    print("outputs peak/rms dBFS")
    for i in range(16): print(f"O{i+1:02d} {db(values[42+i]):7.1f}/{db(values[58+i]):7.1f}", end="  " if i % 2 == 0 else "\n")
def print_probe(port=57120, duration=5):
    duration=max(1, min(30, int(duration))); maximum=[0.0] * 16; deadline=time.time() + duration
    while time.time() < deadline:
        values=get_meters(port)
        for i in range(16): maximum[i]=max(maximum[i], values[i])
        time.sleep(0.5)
    print(f"input probe: {duration}s, signal threshold -80.0 dBFS")
    for i,value in enumerate(maximum): print(f"I{i+1:02d} {'SIGNAL' if db(value) > -80 else 'silence':7s} peak={db(value):7.1f} dBFS")
def tone(output, duration=5, port=57110):
    if not 26 <= output <= 41: raise ValueError("tone output bus must be 26..41")
    sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    node=3100
    # sc_adat_scan is deliberately used directly on a hardware-output bus;
    # it never reads an input or enters the mixer node.
    types=",siiisisfsfsi"
    values=["sc_adat_scan", node, 0, 0, "output", output, "freq", 440.0, "level", -30.0, "gate", 1]
    send(sock, port, packet("/s_new", types, values))
    try:
        time.sleep(max(1, min(5, int(duration))) - 0.5)
    finally:
        send(sock, port, packet("/n_set", ",isi", [node, "gate", 0]))
        time.sleep(0.5)
def main():
    parser=argparse.ArgumentParser(); parser.add_argument("action", choices=("validate", "apply", "serve", "meters", "probe", "tone")); parser.add_argument("config", nargs="?"); parser.add_argument("--port", type=int, default=57110); parser.add_argument("--listen", type=int, default=57120); parser.add_argument("--duration", type=int, default=5); parser.add_argument("--output", type=int); parser.add_argument("--no-node", action="store_true")
    args=parser.parse_args()
    try:
        if args.action == "validate": values, channels=read_config(args.config); print(f"valid mixer config: {len(channels)} channels, inputs/outputs 1..16, capacity 24")
        elif args.action == "apply": apply(args.config, args.port); print("mixer node 3000 applied")
        elif args.action == "meters": print_meters(args.listen)
        elif args.action == "probe": print_probe(args.listen, args.duration)
        elif args.action == "tone": tone(args.output, args.duration, args.port)
        else: serve(args.config, args.listen, args.port, not args.no_node)
    except (OSError, ValueError, OverflowError) as exc: print(f"mixerctl: {exc}", file=sys.stderr); return 1
    return 0
if __name__ == "__main__": sys.exit(main())

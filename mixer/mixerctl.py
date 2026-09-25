#!/usr/bin/env python3
"""Small deterministic OSC/config controller for the transparent SC mixer."""
import argparse, math, os, signal, socket, struct, sys, time

GROUPS = ("kick", "drums", "bass", "music_a", "music_b", "vocals", "fx_a", "fx_b")
MAX_GROUPS = 8
SPATIAL_LIMITS = {
    "kick": (0.5, 0.5, 1.0, 1.0, 0.0, 0.0, 0.5, 1.0, 0.0),
    "drums": (0.25, 0.75, 0.5, 1.0, 0.0, 0.75, 0.5, 0.75, 0.0),
    "bass": (0.5, 0.5, 1.0, 1.0, 0.0, 0.0, 0.5, 1.0, 0.0),
    "music_a": (0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.5, 0.5, 0.5),
    "music_b": (0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.5, 0.5, 0.5),
    "vocals": (0.25, 0.75, 0.5, 1.0, 0.0, 0.5, 0.5, 1.0, 0.0),
    "fx_a": (0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.5, 0.5, 0.5),
    "fx_b": (0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.5, 0.5, 0.5),
}
QUAD_OUTPUTS = ("front_left", "front_right", "rear_left", "rear_right")
BUS_GROUP_STEMS = 52
BUS_DIRECT = 60
BUS_QUAD_GROUPS = 76
BUS_PHYSICAL_OUT = 0
BUS_INPUTS = 26
BUS_RANGES = {"inputs": (BUS_INPUTS, BUS_INPUTS + 26), "group_stems": (BUS_GROUP_STEMS, BUS_GROUP_STEMS + 8), "direct": (BUS_DIRECT, BUS_DIRECT + 16), "quad_group": (BUS_QUAD_GROUPS, BUS_QUAD_GROUPS + 32), "physical_outputs": (BUS_PHYSICAL_OUT, 26)}
assert all(a[1] <= b[0] or b[1] <= a[0] for i,a in enumerate(BUS_RANGES.values()) for j,b in enumerate(BUS_RANGES.values()) if i < j)
FIELDS = ("name", "input", "output", "group", "trim_db", "mute", "polarity", "hpf", "hpf_hz")
METER_WIDTH = 16 + 16 + 8 + 8 + 16 + 16

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
def strict_bool(value, label):
    number=finite(value, label)
    if number not in (0, 1): raise ValueError(f"{label} must be 0 or 1")
    return int(number)
def bounded(value, low, high, label):
    number=finite(value, label)
    if not low <= number <= high: raise ValueError(f"{label} must be {low}..{high}")
    return number
def group_limits(values, name):
    defaults=SPATIAL_LIMITS[name]
    return tuple(float(values.get(f"group.{name}.{key}", defaults[i])) for i,key in enumerate(("x_min","x_max","y_min","y_max","width_min","width_max"))) + defaults[6:]
def validate_parameter(key, numeric, values=None):
    if key == "routingMode" or "Neutral" in key: raise ValueError(f"{key} is configuration-only; restart to change it")
    if key.startswith("trim"): return bounded(numeric, 0.0001, 4, key)
    if key.startswith(("mute", "hpf", "bypass")) or key.endswith(("Mute", "SpatialBypass")): return strict_bool(numeric, key)
    if key.startswith("polarity") or key.endswith("Polarity"):
        number=finite(numeric, key)
        if number not in (-1, 1): raise ValueError(f"{key} must be -1 or 1")
        return number
    if key.startswith("hpfHz"): return bounded(numeric, 20, 20000, key)
    if key.startswith(("groupLevel", "master")): return bounded(numeric, 0, 2, key)
    if key.startswith("group") and "_" in key: raise ValueError(f"{key} is configuration-only; restart to change it")
    if key.endswith(("PosX", "PosY", "Width")):
        index=int(key[5:key.index("Pos")])
        limits=group_limits(values or {}, GROUPS[index])
        low,high=(limits[0],limits[1]) if key.endswith("PosX") else (limits[2],limits[3]) if key.endswith("PosY") else (limits[4],limits[5])
        return bounded(numeric, low, high, key)
    if key == "quadSmoothingMs": return bounded(numeric, 0, 1000, key)
    if key.endswith("GainDb"): return bounded(numeric, -120, 24, key)
    if key.endswith("Bus"): return bounded(numeric, 0, 15, key)
    return finite(numeric, key)
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
    group_count=int(values.get("group.count", str(len(GROUPS))))
    configured_groups=tuple(values.get("group.names", ",".join(GROUPS)).split(","))
    if not 1 <= group_count <= MAX_GROUPS or len(configured_groups) != group_count: raise ValueError("group.count must be 1..8 and match group.names")
    if configured_groups != GROUPS: raise ValueError("production scene must use canonical eight groups")
    mode=values.get("routing.mode", "direct")
    if mode not in ("direct", "quad"): raise ValueError("routing.mode must be direct or quad")
    quad_outputs=[]
    for output in QUAD_OUTPUTS:
        key=f"routing.quad.output.{output}"; number=int(values.get(key, "0"))
        if not 1 <= number <= 16: raise ValueError(f"{key} must be in physical range 1..16")
        quad_outputs.append(number)
    if len(set(quad_outputs)) != 4: raise ValueError("quad physical outputs must be unique")
    for name in configured_groups:
        finite(values[f"group.{name}.level_db"], f"group.{name}.level_db")
        limits=group_limits(values, name)
        for suffix,expected in zip(("x_min","x_max","y_min","y_max","width_min","width_max"), limits[:6]): bounded(expected, 0, 1, f"group.{name}.{suffix}")
        if limits[0] > limits[1] or limits[2] > limits[3] or limits[4] > limits[5]: raise ValueError(f"{name} spatial constraint min exceeds max")
        for suffix, default, low, high in (("pos_x", limits[6], limits[0], limits[1]), ("pos_y", limits[7], limits[2], limits[3]), ("width", limits[8], limits[4], limits[5]), ("neutral_x", limits[6], limits[0], limits[1]), ("neutral_y", limits[7], limits[2], limits[3]), ("neutral_width", limits[8], limits[4], limits[5]), ("spatial_bypass", 0, 0, 1)):
            key=f"group.{name}.{suffix}"; value=values.get(key, str(default))
            if suffix == "spatial_bypass": strict_bool(value, key)
            else: bounded(value, low, high, key)
    bounded(values.get("quad.smoothing_ms", "30"), 0, 1000, "quad.smoothing_ms")
    for n in range(4):
        bounded(values.get(f"quad.output.{n}.gain_db", "0"), -120, 24, f"quad.output.{n}.gain_db")
        strict_bool(values.get(f"quad.output.{n}.mute", "0"), f"quad.output.{n}.mute")
        if int(values.get(f"quad.output.{n}.polarity", "1")) not in (-1, 1): raise ValueError("quad output polarity must be -1 or 1")
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
        result += [(f"group{i}_{g}", int(g == group)) for g in range(MAX_GROUPS)]
    for g,name in enumerate(GROUPS): result.append((f"groupLevel{g}", dbamp(values[f"group.{name}.level_db"])))
    result.append(("master", dbamp(values["master.level_db"]))); result.append(("bypass", as_bool(values["bypass"])))
    for g,name in enumerate(GROUPS):
        limits=group_limits(values, name)
        result += [(f"group{g}PosX", float(values.get(f"group.{name}.pos_x", limits[6]))), (f"group{g}PosY", float(values.get(f"group.{name}.pos_y", limits[7]))), (f"group{g}Width", float(values.get(f"group.{name}.width", limits[8]))), (f"group{g}SpatialBypass", int(values.get(f"group.{name}.spatial_bypass", 0)))]
        result += [(f"group{g}NeutralX", float(values.get(f"group.{name}.neutral_x", limits[6]))), (f"group{g}NeutralY", float(values.get(f"group.{name}.neutral_y", limits[7]))), (f"group{g}NeutralWidth", float(values.get(f"group.{name}.neutral_width", limits[8])))]
    result.append(("quadSmoothingMs", float(values.get("quad.smoothing_ms", 30))))
    for n,output in enumerate(QUAD_OUTPUTS): result += [(f"quadOutput{n}GainDb", float(values.get(f"quad.output.{n}.gain_db", 0))), (f"quadOutput{n}Mute", int(values.get(f"quad.output.{n}.mute", 0))), (f"quadOutput{n}Polarity", int(values.get(f"quad.output.{n}.polarity", 1))), (f"quadOutput{n}Bus", int(values[f"routing.quad.output.{output}"]) - 1)]
    result.append(("routingMode", values.get("routing.mode", "direct")))
    return result
def dsp_controls(values, channels):
    result=[]
    for name,value in controls(values, channels):
        if name == "routingMode": result.append(("quadMode", int(value == "quad"))); continue
        if name == "quadSmoothingMs": result.append(("quadSmoothing", float(value) / 1000.0)); continue
        if "Neutral" in name: continue
        if name.startswith("group") and "_" in name: continue
        if name.endswith("GainDb"): result.append((name[:-5], dbamp(value)))
        else: result.append((name, value))
    for i,row in enumerate(channels): result.append((f"groupSelect{i}", GROUPS.index(row["group"])))
    return result
def send(sock, port, data): sock.sendto(data, ("127.0.0.1", port))
def send_to(sock, address, data): sock.sendto(data, address)
def db(value): return -120.0 if value <= 1e-9 else 20.0 * math.log10(min(1.0, max(1e-9, value)))
ROUTER_NODE=3900; GROUP_NODE_BASE=4000; MASTER_NODE=4100
NODE_ROUTING=1000; NODE_SPATIAL=1001; NODE_MASTER=1002
def send_snew(sock, port, name, node, target, controls_list, action=0):
    vals=[name, node, action, target]; types=",siii"
    for name,value in controls_list:
        if isinstance(value, str): continue
        if name in ("inbus", "outbus", "directbus", "groupbus", "out0", "out1", "out2", "out3"):
            # scsynth controls are numeric OSC values; retain bus identity as
            # an exact integer-valued float so the SynthDef's bus UGen sees
            # the same value as its default/control representation.
            types += "sf"; vals += [name, float(value)]
        else:
            types += "sf"; vals += [name, value]
    send(sock, port, packet("/s_new", types, vals))
def start_graph(sock, port, values, channels):
    sock.settimeout(0.25)
    send(sock, port, packet("/sync", ",i", [1]))
    deadline=time.time()+2.0
    while time.time() < deadline:
        try:
            if parse_packet(sock.recv(65535))[0] == "/synced": break
        except (socket.timeout, ValueError, IndexError): pass
    else: raise RuntimeError("scsynth synchronization failed before graph creation")
    for _ in range(20):
        send(sock, port, packet("/notify", ",i", [1]));
        for node in (ROUTER_NODE, MASTER_NODE, NODE_ROUTING, NODE_SPATIAL, NODE_MASTER):
            send(sock, port, packet("/n_free", ",i", [node]))
        # Build an explicit feed-forward chain.  /g_new action 0 inserts at
        # the head, while action 3 inserts after the target.  The latter is
        # essential here: relying on packet order or repeated add-to-head
        # reverses the execution order seen by In.ar.
        send(sock, port, packet("/g_new", ",iii", [NODE_ROUTING, 0, 0]))
        send(sock, port, packet("/g_new", ",iii", [NODE_SPATIAL, 3, NODE_ROUTING]))
        send(sock, port, packet("/g_new", ",iii", [NODE_MASTER, 3, NODE_SPATIAL]))
        send_snew(sock, port, "sc_adat_router", ROUTER_NODE, NODE_ROUTING, router_controls(values, channels))
        # Add siblings at the tail so the queried tree is 4000..4007.  Their
        # order is not relied on for signal flow, but it is part of the
        # deterministic ownership contract and makes diagnostics unambiguous.
        for g in range(8): send_snew(sock, port, "sc_adat_group", GROUP_NODE_BASE + g, NODE_SPATIAL, group_controls(values, g), action=1)
        send_snew(sock, port, "sc_adat_quad_master", MASTER_NODE, NODE_MASTER, master_controls(values))
        send(sock, port, packet("/sync", ",i", [2])); synced=False; deadline=time.time()+2.0
        while time.time() < deadline and not synced:
            try: path, _, _ = parse_packet(sock.recv(65535))
            except (socket.timeout, ValueError, IndexError): break
            if path == "/synced": synced=True
            if path == "/fail": break
        if synced:
            # Reassert bus controls after node creation.  This is deliberately
            # synchronized: it distinguishes a control-assignment problem
            # from an execution-order problem in the integration test.
            for g in range(8):
                send(sock, port, packet("/n_set", ",isf", [GROUP_NODE_BASE + g, "outbus", float(BUS_QUAD_GROUPS + g * 4)]))
            send(sock, port, packet("/sync", ",i", [3])); deadline=time.time()+2.0
            while time.time() < deadline:
                try:
                    if parse_packet(sock.recv(65535))[0] == "/synced": break
                except (socket.timeout, ValueError, IndexError): pass
            else: raise RuntimeError("scsynth synchronization failed after bus assignment")
            sock.settimeout(None); return
        time.sleep(0.1)
    sock.settimeout(None)
    raise RuntimeError("scsynth did not acknowledge mixer node")
def router_controls(values, channels):
    result=[(n,v) for n,v in dsp_controls(values, channels) if not (n.startswith("group") and "_" in n) and not n.startswith("quadOutput") and not n.startswith("groupLevel") and n not in ("quadMode", "quadSmoothing")]
    result += [(f"groupSelect{i}", GROUPS.index(row["group"])) for i,row in enumerate(channels)]
    result += [(f"level{g}", dbamp(values[f"group.{name}.level_db"])) for g,name in enumerate(GROUPS)]
    result.append(("smoothing", float(values.get("quad.smoothing_ms",30))/1000.0))
    return result
def group_controls(values, g):
    name=GROUPS[g]; limits=group_limits(values, name)
    return [("groupIndex",g),("inbus",BUS_GROUP_STEMS+g),("outbus",BUS_QUAD_GROUPS+g*4),("gain",dbamp(values[f"group.{name}.level_db"])),("mute",0),("x",float(values.get(f"group.{name}.pos_x",limits[6]))*2-1),("y",float(values.get(f"group.{name}.pos_y",limits[7]))*2-1),("width",float(values.get(f"group.{name}.width",limits[8]))),("spatialBypass",int(values.get(f"group.{name}.spatial_bypass",0))), ("xMin",limits[0]*2-1),("xMax",limits[1]*2-1),("yMin",limits[2]*2-1),("yMax",limits[3]*2-1),("widthMin",limits[4]),("widthMax",limits[5]),("neutralX",limits[6]*2-1),("neutralY",limits[7]*2-1),("neutralWidth",limits[8]),("smoothing",float(values.get("quad.smoothing_ms",30))/1000.0)]
def master_controls(values):
    result=[("directbus",BUS_DIRECT),("groupbus",BUS_QUAD_GROUPS),("quadMode",int(values.get("routing.mode")=="quad")),("master",dbamp(values["master.level_db"])),("bypass",as_bool(values["bypass"])),("smoothing",float(values.get("quad.smoothing_ms",30))/1000.0)]
    for n in range(4): result += [(f"quadOutput{n}Gain",dbamp(values.get(f"quad.output.{n}.gain_db",0))),(f"quadOutput{n}Mute",int(values.get(f"quad.output.{n}.mute",0))),(f"quadOutput{n}Polarity",int(values.get(f"quad.output.{n}.polarity",1)))]
    result += [(f"out{i}",int(values[f"routing.quad.output.{name}"])-1) for i,name in enumerate(QUAD_OUTPUTS)]
    return result
def node_update(key, value):
    if key.startswith("group") and key[5:6].isdigit():
        g=int(key[5:key.index("Pos") if "Pos" in key else key.index("Width") if "Width" in key else key.index("Spatial")])
        node=GROUP_NODE_BASE+g
        suffix="x" if key.endswith("PosX") else "y" if key.endswith("PosY") else "width" if key.endswith("Width") else "spatialBypass" if key.endswith("SpatialBypass") else "gain" if key.startswith("groupLevel") else None
        if suffix: return node,suffix,(value*2-1 if suffix in ("x","y") else value)
    if key.startswith("groupLevel"):
        return GROUP_NODE_BASE+int(key[len("groupLevel"):]),"gain",value
    if key.startswith("quadOutput"):
        n=int(key[10:key.index("GainDb") if "GainDb" in key else key.index("Mute") if "Mute" in key else key.index("Polarity") if "Polarity" in key else key.index("Bus")])
        suffix="Gain" if key.endswith("GainDb") else "Mute" if key.endswith("Mute") else "Polarity" if key.endswith("Polarity") else "out%d" % n
        return MASTER_NODE,suffix,(dbamp(value) if key.endswith("GainDb") else value)
    return ROUTER_NODE,key,value
def apply(config, port=57110):
    values, channels=read_config(config); sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); start_graph(sock, port, values, channels); time.sleep(.15); return values, channels
def serve(config, listen=57120, sc_port=57110, start=True):
    values, channels=read_config(config); sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.bind(("0.0.0.0", listen)); initial=controls(values, channels); state=dict(initial); meter_values=[0.0] * METER_WIDTH
    if start: start_graph(sock, sc_port, values, channels)
    def shutdown(_signum, _frame):
        try:
            send(sock, sc_port, packet("/n_set", ",isf", [MASTER_NODE, "master", 0.0])); time.sleep(0.06)
            for node in (NODE_ROUTING, NODE_SPATIAL, NODE_MASTER): send(sock, sc_port, packet("/n_free", ",i", [node]))
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
        elif path == "/mixer/set" and types == ",sf" and len(vals) == 2:
            key, value=vals; allowed={name for name,_ in controls(values, channels)}
            if key not in allowed:
                send_to(sock, address, packet("/mixer/error", ",s", ["invalid parameter"])); continue
            try: numeric=float(value)
            except (TypeError, ValueError): send_to(sock, address, packet("/mixer/error", ",s", ["value is not numeric"])); continue
            if not math.isfinite(numeric): send_to(sock, address, packet("/mixer/error", ",s", ["value must be finite"])); continue
            try: numeric=validate_parameter(key, numeric, values)
            except ValueError as exc:
                send_to(sock, address, packet("/mixer/error", ",s", [str(exc)])); continue
            state[key]=numeric
            if key == "quadSmoothingMs":
                for target in [ROUTER_NODE, MASTER_NODE] + [GROUP_NODE_BASE + g for g in range(8)]: send(sock, sc_port, packet("/n_set", ",isf", [target, "smoothing", numeric / 1000.0]))
            else:
                target,dsp_key,dsp_value=node_update(key, numeric)
                send(sock, sc_port, packet("/n_set", ",isf", [target, dsp_key, dsp_value]))
            send_to(sock, address, packet("/mixer/ok", ",s", [key]))
        elif path == "/mixer/set":
            send_to(sock, address, packet("/mixer/error", ",s", ["expected /mixer/set ,sf parameter value"]))
        elif path == "/mixer/get" and types == ",s":
            key=str(vals[0]) if vals else "master"
            if key not in state: send_to(sock, address, packet("/mixer/error", ",s", ["invalid parameter"]))
            else:
                value=state[key]
                send_to(sock, address, packet("/mixer/state", ",ss", [key, value]) if isinstance(value, str) else packet("/mixer/state", ",sf", [key, value]))
        elif path == "/mixer/get-all" and types == ",":
            for key,value in state.items():
                send_to(sock, address, packet("/mixer/state", ",sf", [key, value]) if not isinstance(value, str) else packet("/mixer/state", ",ss", [key, value]))
            send_to(sock, address, packet("/mixer/get-all-done", ",i", [len(state)]))
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
    for i,name in enumerate(GROUPS): print(f"{name:<11} {db(values[32+i]):7.1f}/{db(values[40+i]):7.1f}")
    print("outputs peak/rms dBFS")
    for i in range(16): print(f"O{i+1:02d} {db(values[48+i]):7.1f}/{db(values[64+i]):7.1f}", end="  " if i % 2 == 0 else "\n")
def print_probe(port=57120, duration=5):
    duration=max(1, min(30, int(duration))); maximum=[0.0] * 16; deadline=time.time() + duration
    while time.time() < deadline:
        values=get_meters(port)
        for i in range(16): maximum[i]=max(maximum[i], values[i])
        time.sleep(0.5)
    print(f"input probe: {duration}s, signal threshold -80.0 dBFS")
    for i,value in enumerate(maximum): print(f"I{i+1:02d} {'SIGNAL' if db(value) > -80 else 'silence':7s} peak={db(value):7.1f} dBFS")
def tone(output, duration=5, port=57110):
    if not 0 <= output <= 15: raise ValueError("tone output bus must be 0..15")
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
        elif args.action == "apply": apply(args.config, args.port); print("mixer graph applied: router, 8 groups, quad master")
        elif args.action == "meters": print_meters(args.listen)
        elif args.action == "probe": print_probe(args.listen, args.duration)
        elif args.action == "tone": tone(args.output, args.duration, args.port)
        else: serve(args.config, args.listen, args.port, not args.no_node)
    except (OSError, ValueError, OverflowError) as exc: print(f"mixerctl: {exc}", file=sys.stderr); return 1
    return 0
if __name__ == "__main__": sys.exit(main())

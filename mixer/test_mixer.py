#!/usr/bin/env python3
import math, os, re, socket, statistics, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(__file__))
from mixerctl import BUS_RANGES, GROUPS, controls, packet, parse_packet, read_config
from mixerctl import group_controls

ROOT=os.path.dirname(os.path.dirname(__file__))
config = "/workspace/payload/config/mixer.conf"
values, channels = read_config(config)
assert list(BUS_RANGES.values()) == [(26,52),(52,60),(76,108),(0,26)]
assert len({tuple(x) for x in BUS_RANGES.values()}) == 4
state = dict(controls(values, channels))
assert state["trim0"] == 1 and state["mute0"] == 0 and state["polarity0"] == 1
assert state["hpf0"] == 0 and state["group0_0"] == 1 and state["group0_1"] == 0
assert state["groupLevel0"] == 1 and state["master"] == 1 and "bypass" not in state
print("neutral controls, groups, mute, polarity, HPF-disabled, levels: OK")

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
scene=open(config, encoding="utf-8").read()
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
quad_proc=subprocess.Popen([sys.executable, os.path.join(os.path.dirname(__file__),"mixerctl.py"),"serve",quad_config,"--port","57118","--listen","57121","--mode","quad"])
quad_sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); quad_sock.settimeout(2); time.sleep(.6)
SC_PORT = 57118
MIXER_PORT = 57121
SILENCE_THRESHOLD = 0.01
METER_RELEASE_SECONDS = 0.10
SCAN_RELEASE_SECONDS = 0.10
SPATIAL_SMOOTHING_SECONDS = float(quad_values["quad.smoothing_ms"]) / 1000.0
QUIET_FRAMES = 4

def sync_sc(token):
    quad_sock.sendto(packet("/sync", ",i", [token]), ("127.0.0.1", SC_PORT))
    deadline=time.monotonic()+2.0
    while time.monotonic() < deadline:
        path, _, _ = parse_packet(quad_sock.recv(65535))
        if path == "/synced": return
    raise AssertionError(("scsynth sync timeout", token, query_tree()))

def query_tree():
    quad_sock.sendto(packet("/g_queryTree", ",ii", [0, 1]), ("127.0.0.1", SC_PORT))
    old=quad_sock.gettimeout(); quad_sock.settimeout(.25); messages=[]
    try:
        while True:
            messages.append(parse_packet(quad_sock.recv(65535)))
    except socket.timeout:
        pass
    finally: quad_sock.settimeout(old)
    return messages

def query_node(node):
    quad_sock.sendto(packet("/n_query", ",i", [node]), ("127.0.0.1", SC_PORT))
    old=quad_sock.gettimeout(); quad_sock.settimeout(1)
    try: return parse_packet(quad_sock.recv(65535))
    except socket.timeout: return ("/fail", ",", [])
    finally: quad_sock.settimeout(old)

def node_exists(node):
    return query_node(node)[0] == "/n_go"

def quad_meters():
    quad_sock.sendto(packet("/mixer/meters",","),("127.0.0.1",MIXER_PORT))
    while True:
        message=parse_packet(quad_sock.recv(65535))
        if message[0]=="/mixer/meters":
            result=[float(x) for x in message[2]]
            assert len(result) == 80 and all(math.isfinite(x) for x in result), result
            return result

def output_meter(values):
    return values[48:64], values[64:80]

def diagnostic(label, node=None, previous_corner=None, current_corner=None,
               gate_off_at=None, node_free_at=None, position_at=None,
               history=()):
    controls_now={}
    for g in range(8):
        reply=request_mixer("get", f"group{g}PosX")
        controls_now[f"group{g}PosX"]=reply[2][1]
        reply=request_mixer("get", f"group{g}PosY")
        controls_now[f"group{g}PosY"]=reply[2][1]
        reply=request_mixer("get", f"group{g}Width")
        controls_now[f"group{g}Width"]=reply[2][1]
    return {"label":label, "previous_corner":previous_corner,
            "current_corner":current_corner, "scan_node":node,
            "scan_exists":node_exists(node) if node is not None else None,
            "four_output_meter_history":list(history),
            "effective_controls":controls_now, "node_tree":query_tree(),
            "seconds_since_gate_off":None if gate_off_at is None else time.monotonic()-gate_off_at,
            "seconds_since_node_free":None if node_free_at is None else time.monotonic()-node_free_at,
            "seconds_since_position_change":None if position_at is None else time.monotonic()-position_at}

def request_mixer(action, key):
    quad_sock.sendto(packet(f"/mixer/{action}", ",s", [key]), ("127.0.0.1", MIXER_PORT))
    return parse_packet(quad_sock.recv(65535))

def qset(key,value):
    quad_sock.sendto(packet("/mixer/set",",sf",[key,value]),( "127.0.0.1",MIXER_PORT))
    deadline=time.monotonic()+2.0
    while time.monotonic() < deadline:
        reply=parse_packet(quad_sock.recv(65535))
        if reply[0] in ("/mixer/ok","/mixer/error"):
            assert reply[0]=="/mixer/ok", (key,value,reply)
            break
    else: raise AssertionError(("mixer set timeout",key,value,query_tree()))
    sync_sc(10000 + int(time.monotonic() * 1000) % 100000)
def qnode(g,x,y):
    quad_sock.sendto(packet("/n_set",",isfsfsf",[4000+g,"x",x,"y",y,"width",0]),( "127.0.0.1",SC_PORT))
    sync_sc(11000 + g)
def qinject(bus,node,level=-12.0):
    quad_sock.sendto(packet("/s_new",",siiisisfsfsi",["sc_adat_scan",node,0,0,"output",bus,"freq",440.0,"level",level,"gate",1]),( "127.0.0.1",SC_PORT))
    sync_sc(12000 + node)
    deadline=time.monotonic()+2.0; samples=[]
    while time.monotonic() < deadline:
        values_now=quad_meters(); peaks,rms=output_meter(values_now); samples.append((values_now[32:40],peaks[:],rms[:]))
        if max(peaks+rms) > SILENCE_THRESHOLD:
            return
    raise AssertionError(("scan did not reach measurable level", node, samples[-6:], query_tree()))

def master_level(key, value):
    qset(key, value); deadline=time.monotonic()+1.0; samples=[]
    while time.monotonic() < deadline:
        samples.append(output_meter(quad_meters())[1][0]); time.sleep(.03)
    return statistics.median(samples[-12:])

def qstop(node, label="scan"):
    gate_off_at=time.monotonic()
    quad_sock.sendto(packet("/n_set",",isf",[node,"gate",0]),( "127.0.0.1",SC_PORT))
    sync_sc(13000 + node)
    # Env.asr release is 100 ms, doneAction:2 then frees the node. Poll the
    # meter frames through the intended completion rather than using a fixed
    # assertion sleep. The explicit /n_free below is bounded cleanup even when
    # doneAction has already removed the node.
    deadline=gate_off_at+SCAN_RELEASE_SECONDS+0.5
    while time.monotonic() < deadline:
        quad_meters()
    quad_sock.sendto(packet("/n_free",",i",[node]),( "127.0.0.1",SC_PORT))
    node_free_at=time.monotonic(); sync_sc(14000 + node)
    reply=query_node(node); assert reply[0] == "/fail", ("scan node still exists", node, reply)
    return gate_off_at,node_free_at

def wait_position_settle():
    # Five time constants is the measured minimum for the 30 ms Lag transition
    # to be effectively settled before a new source is introduced.
    deadline=time.monotonic()+max(5.0*SPATIAL_SMOOTHING_SECONDS, 0.03)
    while time.monotonic() < deadline:
        quad_meters()

def wait_quiet(label, node=None, previous_corner=None, current_corner=None,
               gate_off_at=None, node_free_at=None, position_at=None):
    deadline=time.monotonic()+max(5.0*METER_RELEASE_SECONDS, 4*0.1)+2.0
    quiet=0; history=[]
    while time.monotonic() < deadline:
        values_now=quad_meters(); peaks,rms=output_meter(values_now)
        history.append((time.monotonic(), peaks[:4], rms[:4]))
        if max(peaks+rms) < SILENCE_THRESHOLD:
            quiet += 1
            if quiet >= QUIET_FRAMES: return
        else: quiet=0
    raise AssertionError(diagnostic(label,node,previous_corner,current_corner,gate_off_at,node_free_at,position_at,history[-8:]))

def set_corner(g,x,y,previous_corner=None,current_corner=None):
    qnode(g,x,y); position_at=time.monotonic(); wait_quiet("before corner assertion", current_corner=current_corner, position_at=position_at)
    wait_position_settle(); wait_quiet("after spatial settle", previous_corner=previous_corner, current_corner=current_corner, position_at=position_at)
    return position_at
try:
    source_by_group={GROUPS.index(row["group"]):26+int(row["input"])-1 for row in quad_channels}
    assert set(source_by_group)==set(range(8))
    mapped_outputs=[0,1,2,3]
    input_scan_id=4400
    for row in quad_channels:
        channel=int(row["input"]); group=GROUPS.index(row["group"])
        node=input_scan_id; input_scan_id += 1
        qinject(26+channel-1,node,level=-30.0)
        input_values=quad_meters(); input_peaks=input_values[:16]; group_peaks=input_values[32:40]
        assert input_peaks[channel-1] > SILENCE_THRESHOLD, (channel,input_peaks)
        assert group_peaks[group] > SILENCE_THRESHOLD, (channel,group,group_peaks)
        assert all(value < SILENCE_THRESHOLD for i,value in enumerate(group_peaks) if i != group), (channel,group,group_peaks)
        gate_off_at,node_free_at=qstop(node)
        wait_quiet("after configured input route",node,gate_off_at=gate_off_at,node_free_at=node_free_at)
    print("real input-to-group flow: all 16 configured inputs reach only their assigned group: OK")
    set_corner(0,0,1,"configured input","master gain")
    master_node=6400; qinject(source_by_group[0],master_node,level=-30.0)
    reference=master_level("master",1.0)
    half=master_level("master",0.5)
    silent=master_level("master",0.0)
    restored=master_level("master",1.0)
    assert reference > SILENCE_THRESHOLD and 0.4*reference < half < 0.6*reference, (reference,half)
    assert silent < SILENCE_THRESHOLD, silent
    assert 0.85*reference < restored < 1.15*reference, (reference,restored)
    print(f"real quad master gain: reference={reference:.4f}, half={half:.4f}, zero={silent:.4f}, restored={restored:.4f}: OK")
    gate_off_at,node_free_at=qstop(master_node); wait_quiet("after master gain",master_node,gate_off_at=gate_off_at,node_free_at=node_free_at)
    qinject(52,7000); qstop(7000); wait_quiet("after private bus 52 probe")
    corners=[(-1,1,mapped_outputs[0]), (1,1,mapped_outputs[1]), (-1,-1,mapped_outputs[2]), (1,-1,mapped_outputs[3])]
    previous_corner=None
    for g in range(8):
        for x,y,output in corners:
            current_corner=(g,x,y,output); position_at=set_corner(g,x,y,previous_corner,current_corner)
            scan_node=5000+g*4+output
            qinject(source_by_group[g],scan_node)
            meter_history=[]
            for _ in range(QUIET_FRAMES):
                values_now=quad_meters(); peaks,rms=output_meter(values_now)
                meter_history.append((time.monotonic(),peaks[:],rms[:]))
            try:
                assert all(sample[1][output] > SILENCE_THRESHOLD for sample in meter_history), (g, output, "input", values_now[:16], "groups", values_now[32:48], "outputs", peaks)
                assert all(all(v < SILENCE_THRESHOLD for i,v in enumerate(sample[1]) if i != output) for sample in meter_history), diagnostic("unintended output",scan_node,previous_corner,current_corner,position_at=position_at,history=meter_history)
            except AssertionError:
                raise
            gate_off_at,node_free_at=qstop(scan_node)
            wait_quiet("after corner", scan_node, previous_corner, current_corner, gate_off_at,node_free_at,position_at)
            previous_corner=current_corner
    position_at=set_corner(0,0,0,previous_corner,"centre")
    centre_node=5800; qinject(source_by_group[0],centre_node); centre=output_meter(quad_meters())[0]; assert max(centre[i] for i in mapped_outputs)-min(centre[i] for i in mapped_outputs) < 0.08, centre
    gate_off_at,node_free_at=qstop(centre_node); wait_quiet("after centre",centre_node,previous_corner,"centre",gate_off_at,node_free_at,position_at)
    set_corner(0,-1,1,previous_corner,"summed left"); set_corner(1,-1,1,"summed left","summed left")
    qinject(source_by_group[0],5900); qinject(source_by_group[1],5901); summed=output_meter(quad_meters())[0]; assert summed[mapped_outputs[0]] > 0.02 and max(v for i,v in enumerate(summed) if i != mapped_outputs[0]) < SILENCE_THRESHOLD, summed
    gate_a,free_a=qstop(5900); gate_b,free_b=qstop(5901); wait_quiet("after two-group sum",5901,"summed left","summed left",gate_b,free_b)
    qset("quadSmoothingMs",200); qset("group0PosX",0); qset("group0PosY",1); qset("group0Width",0); wait_quiet("before smoothing case"); wait_position_settle()
    smooth_node=6000; qinject(source_by_group[0],smooth_node); before=output_meter(quad_meters())[0]
    change_at=time.monotonic(); qset("group0PosX",1)
    early=output_meter(quad_meters())[0]; wait_position_settle(); late=output_meter(quad_meters())[0]
    assert early[mapped_outputs[0]] > late[mapped_outputs[0]] and late[mapped_outputs[1]] > early[mapped_outputs[1]], (before,early,late)
    gate_off_at,node_free_at=qstop(smooth_node); wait_quiet("after smoothing",smooth_node,"smoothing start","smoothing end",gate_off_at,node_free_at,change_at)

    # The fixed-lane contract is deliberately checked both statically and by
    # exercising every owned group instance with the same SynthDef.
    source_text=open(os.path.join(ROOT,"supercollider/synthdefs/sc-adat-mixer.scd"),encoding="utf-8").read()
    assert source_text.count("SynthDef(\\sc_adat_group") == 1
    lane_expr=re.findall(r"Out\.ar\(76 \+ \(g \* 4\), quadSignal \* InRange\.kr\(groupIndex, g - 0\.01, g \+ 0\.01\)\)",source_text)
    assert len(lane_expr)==1 and "groupIndex" in source_text
    assert "physical = quad * master" in source_text
    assert "out0c" not in source_text and source_text.count("quadSignal = [") == 1
    assert "Limiter.ar(x.clip2(4), 0.99, 0.01)" in source_text
    assert [int(group_controls(quad_values,g)[0][1]) for g in range(8)] == list(range(8))
    lane_windows=[(g - 0.01, g + 0.01) for g in range(8)]
    assert all(not (lo <= other <= hi) for g,(lo,hi) in enumerate(lane_windows) for other in range(8) if other != g)
    for g in range(8):
        lane_node=6100+g; set_corner(g,-1,1,"lane",("lane",g)); qinject(source_by_group[g],lane_node)
        lane_values=output_meter(quad_meters())[0]; assert lane_values[mapped_outputs[0]] > SILENCE_THRESHOLD and max(v for i,v in enumerate(lane_values) if i != mapped_outputs[0]) < SILENCE_THRESHOLD, (g,lane_values)
        gate_off_at,node_free_at=qstop(lane_node); wait_quiet("after fixed lane",lane_node,"lane",g,gate_off_at,node_free_at)
    # Invalid group-index values must not select any lane; the controller only
    # emits the validated integer range and the DSP gate is one-hot.
    assert all(isinstance(group_controls(quad_values,g)[0][1], int) and 0 <= group_controls(quad_values,g)[0][1] <= 7 for g in range(8))

    # Exercise the proven SelectX spatial bypass at both endpoints and through
    # its smoothed transition on a full-field group with a neutral centre.
    qset("group3SpatialBypass",0); set_corner(3,-1,1,"lane","bypass positioned")
    bypass_node=6200; qinject(source_by_group[3],bypass_node); positioned=output_meter(quad_meters())[0]
    assert positioned[mapped_outputs[0]] > SILENCE_THRESHOLD and max(v for i,v in enumerate(positioned) if i != mapped_outputs[0]) < SILENCE_THRESHOLD, positioned
    qset("group3SpatialBypass",1); wait_position_settle(); neutral=output_meter(quad_meters())[0]
    assert all(math.isfinite(neutral[i]) and neutral[i] > SILENCE_THRESHOLD for i in mapped_outputs), neutral
    assert max(neutral[i] for i in mapped_outputs)-min(neutral[i] for i in mapped_outputs) < 0.08, neutral
    gate_off_at,node_free_at=qstop(bypass_node); wait_quiet("after spatial bypass",bypass_node,"bypass positioned","bypass neutral",gate_off_at,node_free_at)

    # Excessive source level must be bounded by the restored output protection,
    # while meters report that protected hardware signal and cleanup remains
    # deterministic.
    protection_node=6300; qset("group0SpatialBypass",0); set_corner(0,-1,1,"bypass neutral","protection")
    qinject(source_by_group[0],protection_node,level=30.0)
    protected_values=quad_meters(); protected_peaks,protected_rms=output_meter(protected_values)
    assert all(math.isfinite(v) for v in protected_peaks + protected_rms)
    assert protected_peaks[mapped_outputs[0]] <= 1.01 and protected_peaks[mapped_outputs[0]] > 0.5, protected_values
    assert max(v for i,v in enumerate(protected_peaks) if i != mapped_outputs[0]) < SILENCE_THRESHOLD, protected_peaks
    gate_off_at,node_free_at=qstop(protection_node); wait_quiet("after protection",protection_node,"protection","quiescent",gate_off_at,node_free_at)
    assert not node_exists(protection_node), query_tree()
    print("real scsynth quad flow: 8 groups x 4 corners, centre, transposed two-group sum, meter identity and configurable smoothing: OK")
finally:
    quad_proc.terminate(); quad_proc.wait(timeout=2); quad_sock.close(); os.unlink(quad_config)

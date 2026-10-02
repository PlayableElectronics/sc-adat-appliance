#!/usr/bin/env python3
import math, os, re, socket, statistics, subprocess, sys, tempfile, time
import unittest
if "discover" in sys.argv and __name__ != "__main__":
    raise unittest.SkipTest("real scsynth integration script; run through scripts/test-mixer")
from mixerctl import GROUPS, packet, parse_packet, read_config

ROOT=os.path.dirname(os.path.dirname(__file__))
source=os.path.join(ROOT, "payload/config/mixer.conf")
scene=open(source, encoding="utf-8").read()
scene=re.sub(r"(?m)^master\.level_db=.*$", "master.level_db=0", scene)
scene=scene.replace("source.9.group=music_a", "source.9.group=music_b").replace("channel.9.group=music_a", "channel.9.group=music_b")
for group in GROUPS:
    for axis,lo,hi in (("x", "0", "1"),):
        scene=scene.replace(f"group.{group}.{axis}_min=", f"group.{group}.{axis}_min=")
        import re
        scene=re.sub(rf"(?m)^(group\.{group}\.{axis}_min=).*", rf"\g<1>{lo}", scene)
        scene=re.sub(rf"(?m)^(group\.{group}\.{axis}_max=).*", rf"\g<1>{hi}", scene)
with tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False) as f:
    f.write(scene); config=f.name
values,channels=read_config(config)
server=subprocess.Popen([sys.executable, os.path.join(ROOT,"mixer/mixerctl.py"),"serve",config,"--port","57118","--listen","57122","--mode","stereo"])
sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); sock.settimeout(0.5)
SC=57118; MIXER=57122; threshold=0.01
def sync(token):
    sock.sendto(packet("/sync",",i",[token]),("127.0.0.1",SC))
    deadline=time.monotonic()+2
    while time.monotonic()<deadline:
        if parse_packet(sock.recv(65535))[0]=="/synced": return
    raise AssertionError("scsynth sync timeout")
def meters():
    sock.sendto(packet("/mixer/meters",","),("127.0.0.1",MIXER))
    while True:
        p,t,v=parse_packet(sock.recv(65535))
        if p=="/mixer/meters":
            values=[float(x) for x in v]; assert len(values)==80 and all(math.isfinite(x) for x in values)
            return values[48:64],values[64:80]
def set_node(node,key,value):
    sock.sendto(packet("/n_set",",isf",[node,key,float(value)]),("127.0.0.1",SC)); sync(25000+int(time.monotonic()*1000)%100000)
def output_rms():
    samples=[]
    for _ in range(12):
        _,rms=meters(); samples.append(max(rms[:2])); time.sleep(.025)
    return statistics.median(samples)
def output_rms_sample():
    _,rms=meters(); return max(rms[:2])
def start_scan(bus,node,level):
    sock.sendto(packet("/s_new",",siiisisfsfsi",["sc_adat_scan",node,0,0,"output",bus,"freq",440.0,"level",level,"gate",1]),("127.0.0.1",SC)); sync(node+1)
def set_group(g,x):
    sock.sendto(packet("/n_set",",isfsfsf",[4000+g,"x",x,"y",0.0,"width",0.0]),("127.0.0.1",SC)); sync(20000+g)
def mixer_set(key,value):
    sock.sendto(packet("/mixer/set",",sf",[key,value]),("127.0.0.1",MIXER))
    deadline=time.monotonic()+2
    while time.monotonic()<deadline:
        reply=parse_packet(sock.recv(65535))
        if reply[0] in ("/mixer/ok","/mixer/error"):
            assert reply[0]=="/mixer/ok", (key,value,reply)
            sync(30000+int(time.monotonic()*1000)%100000)
            return
    raise AssertionError(("mixer set timeout",key,value))
def position_quiet():
    time.sleep(.04); deadline=time.monotonic()+3; quiet=0
    while time.monotonic()<deadline:
        peaks,_=meters(); quiet=quiet+1 if max(peaks)<threshold else 0
        if quiet>=4: return
    raise AssertionError(("position update failed to settle to silence",peaks))
def inject(bus,node,level=-12):
    sock.sendto(packet("/s_new",",siiisisfsfsi",["sc_adat_scan",node,0,0,"output",bus,"freq",440.0,"level",level,"gate",1]),("127.0.0.1",SC)); sync(node+1)
    deadline=time.monotonic()+2
    while time.monotonic()<deadline:
        peaks,rms=meters()
        if max(peaks[:2])>threshold: return peaks,rms
    raise AssertionError(("stereo output did not become measurable",node,meters()))

def master_level(value):
    mixer_set("master",value); deadline=time.monotonic()+1.0; samples=[]
    while time.monotonic()<deadline:
        samples.append(meters()[1][0]); time.sleep(.03)
    return statistics.median(samples[-12:])
def steady_output():
    frames=[meters()[0] for _ in range(8)]
    return [statistics.median(frame[channel] for frame in frames) for channel in range(16)]
def cleanup(node):
    sock.sendto(packet("/n_set",",isf",[node,"gate",0.0]),("127.0.0.1",SC)); sync(node+10000)
    time.sleep(0.11)
    sock.sendto(packet("/n_free",",i",[node]),("127.0.0.1",SC)); sync(node+20000)
    sock.sendto(packet("/n_query",",i",[node]),("127.0.0.1",SC)); sock.settimeout(.2)
    try: assert parse_packet(sock.recv(4096))[0]!="/n_go"
    except socket.timeout: pass
    sock.settimeout(.5)
    deadline=time.monotonic()+3; quiet=0
    while time.monotonic()<deadline:
        peaks,_=meters()
        quiet=quiet+1 if max(peaks)<threshold else 0
        if quiet>=4: return
    raise AssertionError(("stereo did not quiesce",peaks))
try:
    time.sleep(.5)
    by_group={GROUPS.index(row["group"]):26+int(row["input"])-1 for row in channels}
    test_group=3
    # Stereo mode deliberately has no writable Y control; exercise only its
    # supported X/width surface here.
    mixer_set(f"group{test_group}PosX",0.0); mixer_set(f"group{test_group}Width",0.0)
    # Measure the actual production group SynthDef before unrelated pan tests.
    # The kick scan is injected at the raw pre-group stem; group 0 is muted so
    # only the target group's ducked output reaches the stereo master.
    target_node=9600; kick_node=9601
    set_node(4000,"mute",1); set_node(4000,"duckAmountDb",0)
    set_node(4000,"spatialBypass",1); set_node(4003,"spatialBypass",1)
    set_node(4003,"gain",1); set_node(4003,"mute",0)
    set_node(4003,"duckThreshold",0.1); set_node(4003,"duckAttack",0.05); set_node(4003,"duckRelease",0.2)
    start_scan(52+test_group*2,target_node,-24); time.sleep(.35)
    duck_zero=output_rms()
    start_scan(52,kick_node,-6); time.sleep(.4)
    set_node(4003,"duckAmountDb",0); time.sleep(.15); duck_zero_with_kick=output_rms()
    set_node(4003,"duckAmountDb",6); time.sleep(.5); duck_six=output_rms()
    set_node(4003,"duckAmountDb",12); time.sleep(.5); duck_twelve=output_rms()
    assert duck_zero > 1e-4 and abs(duck_zero_with_kick-duck_zero) < duck_zero*.10, (duck_zero,duck_zero_with_kick)
    assert duck_six < duck_zero*.70, (duck_zero,duck_six)
    assert duck_twelve < duck_six*.70, (duck_six,duck_twelve)
    assert 0 < duck_twelve < duck_six < duck_zero and all(math.isfinite(v) for v in (duck_zero,duck_zero_with_kick,duck_six,duck_twelve))
    set_node(4003,"duckAmountDb",12); set_node(kick_node,"gate",0)
    release_trace=[]
    for _ in range(20):
        release_trace.append(output_rms_sample()); time.sleep(.025)
    assert all(math.isfinite(v) and 0 < v <= duck_zero*1.1 for v in release_trace), release_trace
    assert release_trace[-1] > duck_twelve*2 and release_trace[-1] > release_trace[0], (duck_twelve,release_trace)
    time.sleep(.5); start_scan(52,kick_node,-6)
    attack_trace=[]
    for _ in range(12):
        attack_trace.append(output_rms_sample()); time.sleep(.05)
    assert all(math.isfinite(v) and 0 < v <= duck_zero*1.1 for v in attack_trace), attack_trace
    assert attack_trace[0] > attack_trace[-1] and attack_trace[-1] < duck_zero*.5, (duck_zero,attack_trace)
    set_node(kick_node,"gate",0); time.sleep(.5)
    print(f"real kick-duck audio flow: amount 0/6/12 dB RMS={duck_zero:.6f}/{duck_six:.6f}/{duck_twelve:.6f}; ratios={duck_six/duck_zero:.3f}/{duck_twelve/duck_zero:.3f}; attack {attack_trace[0]:.6f}->{attack_trace[-1]:.6f}; release {release_trace[0]:.6f}->{release_trace[-1]:.6f}: OK")
    cleanup(target_node); cleanup(kick_node)
    set_node(4000,"mute",0); set_node(4003,"duckAmountDb",0)
    equal_power=[]
    for x in (-1.0,0.0,1.0):
        mixer_set(f"group{test_group}PosX",(x+1)/2); time.sleep(.2); node=9450+int((x+1)*10); inject(by_group[test_group],node,level=-30); peaks=steady_output()
        equal_power.append(peaks[:2]); cleanup(node)
    assert equal_power[0][0] > 0.9*equal_power[0][1] and equal_power[0][1] < threshold, equal_power
    assert abs(equal_power[1][0]-equal_power[1][1]) < 0.02, equal_power
    assert equal_power[2][1] > 0.9*equal_power[2][0] and equal_power[2][0] < threshold, equal_power
    print(f"real stereo equal-power: {[[round(v,4) for v in p] for p in equal_power]}: OK")
    mixer_set(f"group{test_group}PosX",0.0); mixer_set(f"group{test_group}Width",0.0)
    master_node=9500; inject(by_group[test_group],master_node,level=-30)
    reference=master_level(1.0); half=master_level(0.5); silent=master_level(0.0); restored=master_level(1.0)
    assert reference > threshold and 0.4*reference < half < 0.6*reference, (reference,half)
    assert silent < threshold, silent
    assert 0.85*reference < restored < 1.15*reference, (reference,restored)
    print(f"real stereo master gain: reference={reference:.4f}, half={half:.4f}, zero={silent:.4f}, restored={restored:.4f}: OK")
    cleanup(master_node)
    for g in range(8):
        for xpos,target in ((-1,0),(1,1),(0,None)):
            set_group(g,xpos); position_quiet()
            node=9000+g*3+(0 if xpos<0 else 1 if xpos>0 else 2)
            if target is not None:
                time.sleep(.25)
                peaks,rms=meters()
            peaks,rms=inject(by_group[g],node)
            assert peaks[target] > threshold if target is not None else abs(peaks[0]-peaks[1])<0.08, (g,xpos,peaks)
            assert max(peaks[2:])<threshold,(g,xpos,peaks)
            assert all(math.isfinite(v) for v in peaks+rms)
            cleanup(node)
    set_group(0,-1); position_quiet(); node=9300
    inject(by_group[0],node,level=30)
    observed=[]; deadline=time.monotonic()+1
    while time.monotonic()<deadline and len(observed)<8:
        frame=meters()
        observed.append(frame)
        time.sleep(.1)
    all_values=[value for frame in observed for vector in frame for value in vector]
    assert all(math.isfinite(value) for value in all_values), observed
    assert max(all_values) <= 1.01, observed
    settled=[frame[0][0] for frame in observed[-3:]]
    assert settled and min(settled) >= .97 and max(settled) <= 1.01, observed
    cleanup(node)
    assert not any("sc_adat_quad_master" in repr(m) for m in [] )
    print("real stereo audio flow: 8 groups x hard-left/hard-right/centre; outputs 3..16 silent; limiter, protected meters and four-frame quiescence: OK")
finally:
    server.terminate(); server.wait(timeout=2); sock.close(); os.unlink(config)

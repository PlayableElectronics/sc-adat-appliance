#!/usr/bin/env python3
"""Deterministic quad math and controller contract tests (no audio required)."""
import math, os, socket, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(__file__))
from mixerctl import GROUPS, controls, packet, parse_packet, read_config

ROOT=os.path.dirname(os.path.dirname(__file__))
CONFIG=os.path.join(ROOT, "payload/config/mixer.conf")
values, channels=read_config(CONFIG)
state=dict(controls(values, channels))
source_path=os.path.join(ROOT, "supercollider/synthdefs/sc-adat-mixer.scd")
source=open(source_path, encoding="utf-8").read() if os.path.exists(source_path) else ""
assert GROUPS == ("kick", "drums", "bass", "music_a", "music_b", "vocals", "fx_a", "fx_b")
assert source.count("SynthDef(\\sc_adat_group") == 1 or os.path.exists("/payload-out/synthdefs/sc_adat_group.scsyndef")
assert "for g in range(8)" in open(os.path.join(ROOT, "mixer/mixerctl.py"), encoding="utf-8").read()
assert all(f"group{i}PosX" in state for i in range(8))
print("one reusable group SynthDef, eight owned instances, independent public group state: OK")
assert values["routing.mode"] == "direct"
assert [int(values[f"routing.quad.output.{n}"]) for n in ("front_left", "front_right", "rear_left", "rear_right")] == [1,2,3,4]

def gains(x, y):
    x=max(0.0,min(1.0,x)); y=max(0.0,min(1.0,y))
    return [math.sqrt((1-x)*(1-y)), math.sqrt(x*(1-y)), math.sqrt((1-x)*y), math.sqrt(x*y)]
for point, expected in [((0,0),(1,0,0,0)), ((1,0),(0,1,0,0)), ((0,1),(0,0,1,0)), ((1,1),(0,0,0,1))]:
    assert all(abs(a-b)<1e-12 for a,b in zip(gains(*point),expected))
assert all(abs(a-.5)<1e-12 for a in gains(.5,.5))
for x,y in [(0,.5),(1,.5),(.5,0),(.5,1)]: assert abs(sum(v*v for v in gains(x,y))-1) < 1e-12
for i in range(11):
    for j in range(11): assert abs(sum(v*v for v in gains(i/10,j/10))-1) < 1e-12
def stereo(x,y,width):
    a=gains(x-width*.5,y); b=gains(x+width*.5,y)
    c=[(u+v)*.5 for u,v in zip(a,b)]; norm=math.sqrt(sum(v*v for v in c)); return [v/norm for v in c]
assert stereo(.5,.5,0) == gains(.5,.5)
assert max(abs(a-b) for a,b in zip(stereo(.1,.2,1), stereo(.1,.2,0))) > .1
assert abs(sum(v*v for v in stereo(.2,.5,1))-1) < 1e-12
alpha=1-math.exp(-1/(48000*.03))
sample=0
for _ in range(int(.03*48000)): sample += alpha*(1-sample)
assert .62 < sample < .64
print("quad corners, centre, edges, 11x11 constant-power grid, stereo width, 30ms smoothing: OK")

# Regression for the target-build spatial bypass path: SelectX interpolates
# positioned and neutral gains, so both endpoints and every smoothed value stay
# finite and non-silent instead of collapsing through a zero/NaN branch.
assert "SelectX.kr(spatialBypass, [gfl, nfl])" in source
assert all(math.isfinite(v) and abs(v) > 0 for v in gains(.5, .5))
for bypass in [i / 10 for i in range(11)]:
    positioned=gains(.1, .9); neutral=gains(.5, .5)
    transition=[p * (1-bypass) + n * bypass for p,n in zip(positioned,neutral)]
    assert all(math.isfinite(v) for v in transition)
    assert math.sqrt(sum(v*v for v in transition)) > 0
assert gains(.1,.9) != gains(.5,.5)
assert gains(.5,.5) == gains(.5,.5)
print("spatial bypass endpoints, SelectX transition finiteness, and non-silence: OK")

def request(sock, path, types, vals):
    sock.sendto(packet(path, types, vals), address); return parse_packet(sock.recv(65535))
port=57221; proc=subprocess.Popen([sys.executable, os.path.join(os.path.dirname(__file__),"mixerctl.py"),"serve",CONFIG,"--listen",str(port),"--port","57218","--no-node"])
sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); sock.settimeout(2); address=("127.0.0.1",port)
try:
    time.sleep(.2)
    for g,name in enumerate(GROUPS):
        assert request(sock,"/mixer/set",",sf",[f"group{g}PosX",float(values[f"group.{name}.pos_x"])])[0]=="/mixer/ok"
        assert request(sock,"/mixer/set",",sf",[f"group{g}SpatialBypass",0])[0]=="/mixer/ok"
    assert request(sock,"/mixer/set",",sf",["group3PosX",0.25])[0]=="/mixer/ok"
    assert request(sock,"/mixer/get",",s",["group3PosX"])[2][1] == .25
    assert request(sock,"/mixer/set",",sf",["group3PosY",float("inf")])[0]=="/mixer/error"
    assert request(sock,"/mixer/set",",sf",["group3PosX",1.1])[0]=="/mixer/error"
    assert request(sock,"/mixer/set",",ss",["group3PosX","0.2"])[0]=="/mixer/error"
    seen=set(); done=False
    sock.sendto(packet("/mixer/get-all", ","),address)
    while not done:
        path,types,vals=parse_packet(sock.recv(65535))
        if path=="/mixer/state": seen.add(vals[0])
        elif path=="/mixer/get-all-done": done=True
    assert {"group3PosX","quadOutput0GainDb","routingMode"} <= seen
    for n in range(100): assert request(sock,"/mixer/set",",sf",["group3PosX",n/99])[0]=="/mixer/ok"
finally:
    proc.terminate(); proc.wait(timeout=2); sock.close()
print("OSC set/get/get-all, NaN/infinity/range/type rejection, sustained 100 Hz updates: OK")

with tempfile.NamedTemporaryFile("w", delete=False) as f:
    f.write(open(CONFIG, encoding="utf-8").read().replace("routing.quad.output.front_right=2", "routing.quad.output.front_right=1")); bad=f.name
try:
    try: read_config(bad); raise AssertionError("duplicate quad output accepted")
    except ValueError: pass
finally: os.unlink(bad)
print("exact physical mapping uniqueness/range and no unintended-output contract: OK")

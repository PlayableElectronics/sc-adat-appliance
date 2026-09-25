// Reusable-node mixer graph. The controller owns node IDs and lifecycle.
// Coordinates use X=-1 left/+1 right and Y=-1 rear/+1 front internally.
SynthDef(\sc_adat_router, {
  var inputs = In.ar(26, 16), trim, mute, polarity, hpf, hpfHz, groupSelect, channels, groupSignals, smoothing = NamedControl.kr(\smoothing, 0.03);
  trim = Array.fill(16, { |i| NamedControl.kr(("trim" ++ i).asSymbol, 1) });
  mute = Array.fill(16, { |i| NamedControl.kr(("mute" ++ i).asSymbol, 0) });
  polarity = Array.fill(16, { |i| NamedControl.kr(("polarity" ++ i).asSymbol, 1) });
  hpf = Array.fill(16, { |i| NamedControl.kr(("hpf" ++ i).asSymbol, 0) });
  hpfHz = Array.fill(16, { |i| NamedControl.kr(("hpfHz" ++ i).asSymbol, 80) });
  groupSelect = Array.fill(16, { |i| NamedControl.kr(("groupSelect" ++ i).asSymbol, ((i div: 2) min: 7)) });
  trim = trim.collect { |x| Lag.kr(x.clip(0.0001, 4), smoothing) }; mute = mute.collect { |x| Lag.kr(x.clip(0, 1), smoothing) }; polarity = polarity.collect { |x| Lag.kr(x.clip(-1, 1), smoothing) }; hpf = hpf.collect { |x| Lag.kr(x.clip(0, 1), smoothing) }; hpfHz = hpfHz.collect { |x| Lag.kr(x.clip(20, 20000), smoothing) };
  channels = inputs.collect { |sig, i| var filtered = SelectX.ar(hpf[i], [sig, HPF.ar(sig, hpfHz[i])]); filtered * trim[i] * (1 - mute[i]) * polarity[i] };
  groupSignals = Array.fill(8, { |g| Mix(channels.collect { |sig, i| sig * InRange.kr(groupSelect[i], g - 0.01, g + 0.01) }) });
  8.do { |g| Out.ar(52 + g, groupSignals[g]) };
  SendReply.kr(Impulse.kr(10), "/mixer/router-meter", channels.collect { |x| Amplitude.kr(x, 0.01, 0.1) } ++ channels.collect { |x| Lag.kr(A2K.kr(x.squared), 0.1).sqrt });
}).writeDefFile("/payload-out");

SynthDef(\sc_adat_group, { |inbus=52, outbus=76|
  var sig = In.ar(inbus, 1), groupIndex = NamedControl.kr(\groupIndex, 0), gain = NamedControl.kr(\gain, 1), mute = NamedControl.kr(\mute, 0);
  var x = NamedControl.kr(\x, 0), y = NamedControl.kr(\y, 1), width = NamedControl.kr(\width, 0);
  var spatialBypass = NamedControl.kr(\spatialBypass, 0), xMin = NamedControl.kr(\xMin, -1), xMax = NamedControl.kr(\xMax, 1);
  var yMin = NamedControl.kr(\yMin, -1), yMax = NamedControl.kr(\yMax, 1), widthMin = NamedControl.kr(\widthMin, 0), widthMax = NamedControl.kr(\widthMax, 1);
  var neutralX = NamedControl.kr(\neutralX, 0), neutralY = NamedControl.kr(\neutralY, 1), neutralWidth = NamedControl.kr(\neutralWidth, 0);
  var sx, sy, sw, left, right, norm, neutralNorm, yy, fl, fr, rl, rr, gfl, gfr, grl, grr, nfl, nfr, nrl, nrr, base, quadSignal, smoothing = NamedControl.kr(\smoothing, 0.03);
  gain = Lag.kr(gain.clip(0.0001, 2), smoothing); mute = Lag.kr(mute.clip(0, 1), smoothing); x = Lag.kr(x.clip(xMin, xMax), smoothing); y = Lag.kr(y.clip(yMin, yMax), smoothing); width = Lag.kr(width.clip(widthMin, widthMax), smoothing); spatialBypass = Lag.kr(spatialBypass.clip(0, 1), smoothing);
  sx = x.clip(xMin, xMax); sy = y.clip(yMin, yMax); sw = width.clip(widthMin, widthMax);
  left = (((sx - sw + 1) * 0.5).clip(0, 1)); right = (((sx + sw + 1) * 0.5).clip(0, 1));
  yy = ((sy + 1) * 0.5).clip(0, 1); fl = (((1-left) * yy).sqrt + ((1-right) * yy).sqrt) * 0.5; fr = ((left * yy).sqrt + (right * yy).sqrt) * 0.5; rl = (((1-left) * (1-yy)).sqrt + ((1-right) * (1-yy)).sqrt) * 0.5; rr = ((left * (1-yy)).sqrt + (right * (1-yy)).sqrt) * 0.5;
  norm = (fl.squared + fr.squared + rl.squared + rr.squared).sqrt.max(0.0001); gfl = fl / norm; gfr = fr / norm; grl = rl / norm; grr = rr / norm;
  left = (((neutralX - neutralWidth + 1) * 0.5).clip(0, 1)); right = (((neutralX + neutralWidth + 1) * 0.5).clip(0, 1)); yy = ((neutralY + 1) * 0.5).clip(0, 1); fl = (((1-left) * yy).sqrt + ((1-right) * yy).sqrt) * 0.5; fr = ((left * yy).sqrt + (right * yy).sqrt) * 0.5; rl = (((1-left) * (1-yy)).sqrt + ((1-right) * (1-yy)).sqrt) * 0.5; rr = ((left * (1-yy)).sqrt + (right * (1-yy)).sqrt) * 0.5;
  neutralNorm = (fl.squared + fr.squared + rl.squared + rr.squared).sqrt.max(0.0001);
  nfl = fl / neutralNorm; nfr = fr / neutralNorm; nrl = rl / neutralNorm; nrr = rr / neutralNorm; base = sig * gain * (1 - mute);
  quadSignal = [
    base * SelectX.kr(spatialBypass, [gfl, nfl]),
    base * SelectX.kr(spatialBypass, [gfr, nfr]),
    base * SelectX.kr(spatialBypass, [grl, nrl]),
    base * SelectX.kr(spatialBypass, [grr, nrr])
  ];
  // The target scsynth build does not reliably evaluate a control-rate bus
  // selector as Out.ar's destination. Keep one reusable group SynthDef and
  // write the eight fixed private lane tuples, gating only the lane owned by
  // groupIndex. The controller's validated outbus remains in node state and
  // is asserted against the canonical lane during startup.
  8.do { |g| Out.ar(76 + (g * 4), quadSignal * InRange.kr(groupIndex, g - 0.01, g + 0.01)) };
}).writeDefFile("/payload-out");

SynthDef(\sc_adat_quad_master, {
  var rawInputs = In.ar(26, 16), groupStems = In.ar(52, 8), g0 = In.ar(76, 4), g1 = In.ar(80, 4), g2 = In.ar(84, 4), g3 = In.ar(88, 4), g4 = In.ar(92, 4), g5 = In.ar(96, 4), g6 = In.ar(100, 4), g7 = In.ar(104, 4);
  // The group layout is eight consecutive four-speaker tuples. Keep the
  // transpose explicit: each master speaker sums one component from all
  // eight groups, never all four components from one group.
  var quad = [
    g0[0] + g1[0] + g2[0] + g3[0] + g4[0] + g5[0] + g6[0] + g7[0],
    g0[1] + g1[1] + g2[1] + g3[1] + g4[1] + g5[1] + g6[1] + g7[1],
    g0[2] + g1[2] + g2[2] + g3[2] + g4[2] + g5[2] + g6[2] + g7[2],
    g0[3] + g1[3] + g2[3] + g3[3] + g4[3] + g5[3] + g6[3] + g7[3]
  ];
  var master = NamedControl.kr(\master, 1);
  var physical, output, smoothing = NamedControl.kr(\smoothing, 0.03);
  master = Lag.kr(master.clip(0, 2), smoothing);
  physical = quad * master;
  output = physical.collect { |x| Limiter.ar(x.clip2(4), 0.99, 0.01) };
  Out.ar(0, output);
  SendReply.kr(Impulse.kr(10), "/mixer/meter", rawInputs.collect { |x| Amplitude.kr(x, 0.01, 0.1) } ++ rawInputs.collect { |x| Lag.kr(A2K.kr(x.squared), 0.1).sqrt } ++ groupStems.collect { |x| Amplitude.kr(x, 0.01, 0.1) } ++ groupStems.collect { |x| Lag.kr(A2K.kr(x.squared), 0.1).sqrt } ++ output.collect { |x| Amplitude.kr(x, 0.01, 0.1) } ++ Array.fill(12, { 0 }) ++ output.collect { |x| Lag.kr(A2K.kr(x.squared), 0.1).sqrt } ++ Array.fill(12, { 0 }));
}).writeDefFile("/payload-out");

SynthDef(\sc_adat_stereo_master, {
  var rawInputs = In.ar(26, 16), groupStems = In.ar(52, 8), g0 = In.ar(76, 4), g1 = In.ar(80, 4), g2 = In.ar(84, 4), g3 = In.ar(88, 4), g4 = In.ar(92, 4), g5 = In.ar(96, 4), g6 = In.ar(100, 4), g7 = In.ar(104, 4);
  var left = g0[0] + g0[2] + g1[0] + g1[2] + g2[0] + g2[2] + g3[0] + g3[2] + g4[0] + g4[2] + g5[0] + g5[2] + g6[0] + g6[2] + g7[0] + g7[2];
  var right = g0[1] + g0[3] + g1[1] + g1[3] + g2[1] + g2[3] + g3[1] + g3[3] + g4[1] + g4[3] + g5[1] + g5[3] + g6[1] + g6[3] + g7[1] + g7[3];
  var master = NamedControl.kr(\master, 1), smoothing = NamedControl.kr(\smoothing, 0.03), output;
  master = Lag.kr(master.clip(0, 2), smoothing);
  output = [left, right].collect { |x| Limiter.ar((x * master).clip2(4), 0.99, 0.01) };
  Out.ar(0, output);
  SendReply.kr(Impulse.kr(10), "/mixer/meter", rawInputs.collect { |x| Amplitude.kr(x, 0.01, 0.1) } ++ rawInputs.collect { |x| Lag.kr(A2K.kr(x.squared), 0.1).sqrt } ++ groupStems.collect { |x| Amplitude.kr(x, 0.01, 0.1) } ++ groupStems.collect { |x| Lag.kr(A2K.kr(x.squared), 0.1).sqrt } ++ output.collect { |x| Amplitude.kr(x, 0.01, 0.1) } ++ Array.fill(14, { 0 }) ++ output.collect { |x| Lag.kr(A2K.kr(x.squared), 0.1).sqrt } ++ Array.fill(14, { 0 }));
}).writeDefFile("/payload-out");

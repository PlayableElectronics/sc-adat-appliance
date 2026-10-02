// Reusable-node mixer graph. The controller owns node IDs and lifecycle.
// Coordinates use X=-1 left/+1 right and Y=-1 rear/+1 front internally.
SynthDef(\sc_adat_router, {
  var inputs = In.ar(26, 16), mode = NamedControl.kr(\sourceMode, 0), inputL = NamedControl.kr(\sourceInputL, 0), inputR = NamedControl.kr(\sourceInputR, 0), group = NamedControl.kr(\sourceGroup, 0);
  var trim = NamedControl.kr(\sourceTrim, 1), mute = NamedControl.kr(\sourceMute, 0), polarityL = NamedControl.kr(\sourcePolarityL, 1), polarityR = NamedControl.kr(\sourcePolarityR, 1);
  var hpf = NamedControl.kr(\sourceHPF, 0), hpfHz = NamedControl.kr(\sourceHPFHz, 80), pan = NamedControl.kr(\sourcePan, 0), balance = NamedControl.kr(\sourceBalance, 0), width = NamedControl.kr(\sourceWidth, 1), smoothing = NamedControl.kr(\smoothing, 0.03);
  var left, right, filteredL, filteredR, monoLeft, monoRight, mid, side, stereoLeft, stereoRight, sourceLeft, sourceRight, selected;
  trim = Lag.kr(trim.clip(0.0001, 4), smoothing); mute = Lag.kr(mute.clip(0, 1), smoothing); polarityL = Lag.kr(polarityL.clip(-1, 1), smoothing); polarityR = Lag.kr(polarityR.clip(-1, 1), smoothing); hpf = Lag.kr(hpf.clip(0, 1), smoothing); hpfHz = Lag.kr(hpfHz.clip(20, 20000), smoothing); pan = Lag.kr(pan.clip(-1, 1), smoothing); balance = Lag.kr(balance.clip(-1, 1), smoothing); width = Lag.kr(width.clip(0, 1), smoothing);
  left = Select.ar(inputL.clip(0, 15), inputs); right = Select.ar(inputR.clip(0, 15), inputs);
  filteredL = SelectX.ar(hpf, [left, HPF.ar(left, hpfHz)]) * polarityL; filteredR = SelectX.ar(hpf, [right, HPF.ar(right, hpfHz)]) * polarityR;
  monoLeft = filteredL * ((pan + 1) * 0.25 * pi).cos; monoRight = filteredL * ((pan + 1) * 0.25 * pi).sin;
  mid = (filteredL + filteredR) * 0.5; side = (filteredL - filteredR) * 0.5 * width;
  stereoLeft = (mid + side) * (((1 - balance).clip(0, 2) * 0.5).sqrt * 2.sqrt); stereoRight = (mid - side) * (((1 + balance).clip(0, 2) * 0.5).sqrt * 2.sqrt);
  sourceLeft = SelectX.ar(mode, [monoLeft, stereoLeft]) * trim * (1 - mute); sourceRight = SelectX.ar(mode, [monoRight, stereoRight]) * trim * (1 - mute);
  8.do { |g| selected = InRange.kr(group, g - 0.01, g + 0.01); Out.ar(52 + (g * 2), [sourceLeft, sourceRight] * selected) };
}).writeDefFile("/payload-out");

SynthDef(\sc_adat_group, { |inbus=52, outbus=76|
  var sig = In.ar(inbus, 2), groupIndex = NamedControl.kr(\groupIndex, 0), gain = NamedControl.kr(\gain, 1), mute = NamedControl.kr(\mute, 0);
  var x = NamedControl.kr(\x, 0), y = NamedControl.kr(\y, 1), width = NamedControl.kr(\width, 0);
  var spatialBypass = NamedControl.kr(\spatialBypass, 0), xMin = NamedControl.kr(\xMin, -1), xMax = NamedControl.kr(\xMax, 1);
  var yMin = NamedControl.kr(\yMin, -1), yMax = NamedControl.kr(\yMax, 1), widthMin = NamedControl.kr(\widthMin, 0), widthMax = NamedControl.kr(\widthMax, 1);
  var neutralX = NamedControl.kr(\neutralX, 0), neutralY = NamedControl.kr(\neutralY, 1), neutralWidth = NamedControl.kr(\neutralWidth, 0);
  var sx, sy, sw, left, right, norm, neutralNorm, yy, fl, fr, rl, rr, gfl, gfr, grl, grr, nfl, nfr, nrl, nrr, baseLeft, baseRight, quadSignal, smoothing = NamedControl.kr(\smoothing, 0.03);
  gain = Lag.kr(gain.clip(0.0001, 2), smoothing); mute = Lag.kr(mute.clip(0, 1), smoothing); x = Lag.kr(x.clip(xMin, xMax), smoothing); y = Lag.kr(y.clip(yMin, yMax), smoothing); width = Lag.kr(width.clip(widthMin, widthMax), smoothing); spatialBypass = Lag.kr(spatialBypass.clip(0, 1), smoothing);
  sx = x.clip(xMin, xMax); sy = y.clip(yMin, yMax); sw = width.clip(widthMin, widthMax);
  left = (((sx - sw + 1) * 0.5).clip(0, 1)); right = (((sx + sw + 1) * 0.5).clip(0, 1));
  yy = ((sy + 1) * 0.5).clip(0, 1); fl = (((1-left) * yy).sqrt + ((1-right) * yy).sqrt) * 0.5; fr = ((left * yy).sqrt + (right * yy).sqrt) * 0.5; rl = (((1-left) * (1-yy)).sqrt + ((1-right) * (1-yy)).sqrt) * 0.5; rr = ((left * (1-yy)).sqrt + (right * (1-yy)).sqrt) * 0.5;
  norm = (fl.squared + fr.squared + rl.squared + rr.squared).sqrt.max(0.0001); gfl = fl / norm; gfr = fr / norm; grl = rl / norm; grr = rr / norm;
  left = (((neutralX - neutralWidth + 1) * 0.5).clip(0, 1)); right = (((neutralX + neutralWidth + 1) * 0.5).clip(0, 1)); yy = ((neutralY + 1) * 0.5).clip(0, 1); fl = (((1-left) * yy).sqrt + ((1-right) * yy).sqrt) * 0.5; fr = ((left * yy).sqrt + (right * yy).sqrt) * 0.5; rl = (((1-left) * (1-yy)).sqrt + ((1-right) * (1-yy)).sqrt) * 0.5; rr = ((left * (1-yy)).sqrt + (right * (1-yy)).sqrt) * 0.5;
  neutralNorm = (fl.squared + fr.squared + rl.squared + rr.squared).sqrt.max(0.0001);
  nfl = fl / neutralNorm; nfr = fr / neutralNorm; nrl = rl / neutralNorm; nrr = rr / neutralNorm;
  baseLeft = sig[0] * gain * (1 - mute); baseRight = sig[1] * gain * (1 - mute);
  // A stereo source remains oriented at the group boundary.  Spatial
  // positioning controls the amount sent to the four internal lanes, while
  // left never becomes right and vice versa.
  quadSignal = [
    baseLeft * SelectX.kr(spatialBypass, [gfl, nfl]),
    baseRight * SelectX.kr(spatialBypass, [gfr, nfr]),
    baseLeft * SelectX.kr(spatialBypass, [grl, nrl]),
    baseRight * SelectX.kr(spatialBypass, [grr, nrr])
  ];
  // The target scsynth build does not reliably evaluate a control-rate bus
  // selector as Out.ar's destination. Keep one reusable group SynthDef and
  // write the eight fixed private lane tuples, gating only the lane owned by
  // groupIndex. The controller's validated outbus remains in node state and
  // is asserted against the canonical lane during startup.
  8.do { |g| Out.ar(76 + (g * 4), quadSignal * InRange.kr(groupIndex, g - 0.01, g + 0.01)) };
}).writeDefFile("/payload-out");

SynthDef(\sc_adat_stereo_group, { |inbus=52, outbus=76|
  var sig = In.ar(inbus, 2), groupIndex = NamedControl.kr(\groupIndex, 0), gain = NamedControl.kr(\gain, 1), mute = NamedControl.kr(\mute, 0);
  var x = NamedControl.kr(\x, 0), y = NamedControl.kr(\y, 1), width = NamedControl.kr(\width, 0);
  var spatialBypass = NamedControl.kr(\spatialBypass, 0), xMin = NamedControl.kr(\xMin, -1), xMax = NamedControl.kr(\xMax, 1);
  var yMin = NamedControl.kr(\yMin, -1), yMax = NamedControl.kr(\yMax, 1), widthMin = NamedControl.kr(\widthMin, 0), widthMax = NamedControl.kr(\widthMax, 1);
  var neutralX = NamedControl.kr(\neutralX, 0), neutralY = NamedControl.kr(\neutralY, 1), neutralWidth = NamedControl.kr(\neutralWidth, 0);
  var eqBypass=NamedControl.kr(\eqBypass,1), eqLowDb=NamedControl.kr(\eqLowDb,0), eqLowHz=NamedControl.kr(\eqLowHz,100), eqLowMidDb=NamedControl.kr(\eqLowMidDb,0), eqLowMidHz=NamedControl.kr(\eqLowMidHz,400), eqHighMidDb=NamedControl.kr(\eqHighMidDb,0), eqHighMidHz=NamedControl.kr(\eqHighMidHz,2500), eqHighDb=NamedControl.kr(\eqHighDb,0), eqHighHz=NamedControl.kr(\eqHighHz,8000);
  var compBypass=NamedControl.kr(\compBypass,1), compThresholdDb=NamedControl.kr(\compThresholdDb,-18), compRatio=NamedControl.kr(\compRatio,2), compAttack=NamedControl.kr(\compAttack,0.01), compRelease=NamedControl.kr(\compRelease,0.15);
  var satBypass=NamedControl.kr(\satBypass,1), satDrive=NamedControl.kr(\satDrive,1);
  var duckAmountDb=NamedControl.kr(\duckAmountDb,0), duckThreshold=NamedControl.kr(\duckThreshold,0.1), duckAttack=NamedControl.kr(\duckAttack,0.01), duckRelease=NamedControl.kr(\duckRelease,0.2);
  var sx, sy, sw, left, right, norm, neutralNorm, yy, fl, fr, rl, rr, gfl, gfr, grl, grr, nfl, nfr, nrl, nrr, baseLeft, baseRight, quadSignal, smoothing = NamedControl.kr(\smoothing, 0.03);
  var detector, envelope, duckGain, dry, eq, compressed, saturated, processed, compThreshold, linkedDetector;
  gain = Lag.kr(gain.clip(0.0001, 2), smoothing); mute = Lag.kr(mute.clip(0, 1), smoothing); x = Lag.kr(x.clip(xMin, xMax), smoothing); y = Lag.kr(y.clip(yMin, yMax), smoothing); width = Lag.kr(width.clip(widthMin, widthMax), smoothing); spatialBypass = Lag.kr(spatialBypass.clip(0, 1), smoothing);
  sx = x.clip(xMin, xMax); sy = y.clip(yMin, yMax); sw = width.clip(widthMin, widthMax);
  left = (((sx - sw + 1) * 0.5).clip(0, 1)); right = (((sx + sw + 1) * 0.5).clip(0, 1));
  yy = ((sy + 1) * 0.5).clip(0, 1); fl = (((1-left) * yy).sqrt + ((1-right) * yy).sqrt) * 0.5; fr = ((left * yy).sqrt + (right * yy).sqrt) * 0.5; rl = (((1-left) * (1-yy)).sqrt + ((1-right) * (1-yy)).sqrt) * 0.5; rr = ((left * (1-yy)).sqrt + (right * (1-yy)).sqrt) * 0.5;
  norm = (fl.squared + fr.squared + rl.squared + rr.squared).sqrt.max(0.0001); gfl = fl / norm; gfr = fr / norm; grl = rl / norm; grr = rr / norm;
  left = (((neutralX - neutralWidth + 1) * 0.5).clip(0, 1)); right = (((neutralX + neutralWidth + 1) * 0.5).clip(0, 1)); yy = ((neutralY + 1) * 0.5).clip(0, 1); fl = (((1-left) * yy).sqrt + ((1-right) * yy).sqrt) * 0.5; fr = ((left * yy).sqrt + (right * yy).sqrt) * 0.5; rl = (((1-left) * (1-yy)).sqrt + ((1-right) * (1-yy)).sqrt) * 0.5; rr = ((left * (1-yy)).sqrt + (right * (1-yy)).sqrt) * 0.5;
  neutralNorm = (fl.squared + fr.squared + rl.squared + rr.squared).sqrt.max(0.0001);
  nfl = fl / neutralNorm; nfr = fr / neutralNorm; nrl = rl / neutralNorm; nrr = rr / neutralNorm;
  // Detector taps the kick group's source stem, before its group processors.
  detector = In.ar(52, 2).sum * 0.5;
  envelope = Amplitude.kr(detector, 0.001, 0.05);
  duckGain = 1 - (envelope > duckThreshold.clip(0.001, 1)) * (1 - (10 ** (duckAmountDb.clip(0, 18) / 20)));
  duckGain = LagUD.kr(duckGain, duckAttack.clip(0.001,0.5), duckRelease.clip(0.01,2));
  dry=sig;
  // Mid bands are applied serially on the equalized branch.
  eq=dry.collect { |channel| var wet=BLowShelf.ar(channel,eqLowHz.clip(40,500),1,eqLowDb.clip(-12,12)); wet=BPeakEQ.ar(wet,eqLowMidHz.clip(100,2000),1,eqLowMidDb.clip(-12,12)); wet=BPeakEQ.ar(wet,eqHighMidHz.clip(500,8000),1,eqHighMidDb.clip(-12,12)); wet=BHiShelf.ar(wet,eqHighHz.clip(2000,16000),1,eqHighDb.clip(-12,12)); SelectX.ar(eqBypass.clip(0,1),[wet,channel]) };
  compThreshold=10 ** (compThresholdDb.clip(-60,0)/20);
  linkedDetector=eq[0].abs.max(eq[1].abs);
  compressed=eq.collect { |channel| var wet=Compander.ar(channel,linkedDetector,compThreshold,1,1/compRatio.clip(1,20),compAttack.clip(0.001,0.5),compRelease.clip(0.01,2)); SelectX.ar(compBypass.clip(0,1),[wet,channel]) };
  satDrive=satDrive.clip(1,4);
  processed=compressed.collect { |channel| var wet=tanh(channel*satDrive)/tanh(satDrive); SelectX.ar(satBypass.clip(0,1),[wet,channel]) };
  processed=processed * duckGain;
  baseLeft = processed[0] * gain * (1 - mute); baseRight = processed[1] * gain * (1 - mute);
  // A stereo source remains oriented at the group boundary.  Spatial
  // positioning controls the amount sent to the four internal lanes, while
  // left never becomes right and vice versa.
  quadSignal = [
    baseLeft * SelectX.kr(spatialBypass, [gfl, nfl]),
    baseRight * SelectX.kr(spatialBypass, [gfr, nfr]),
    baseLeft * SelectX.kr(spatialBypass, [grl, nrl]),
    baseRight * SelectX.kr(spatialBypass, [grr, nrr])
  ];
  // The target scsynth build does not reliably evaluate a control-rate bus
  // selector as Out.ar's destination. Keep one reusable group SynthDef and
  // write the eight fixed private lane tuples, gating only the lane owned by
  // groupIndex. The controller's validated outbus remains in node state and
  // is asserted against the canonical lane during startup.
  8.do { |g| Out.ar(76 + (g * 4), quadSignal * InRange.kr(groupIndex, g - 0.01, g + 0.01)) };
}).writeDefFile("/payload-out");

SynthDef(\sc_adat_test_generator, {
  var kind=NamedControl.kr(\kind,0), destination=NamedControl.kr(\destination,0), level=NamedControl.kr(\level,0.01), timeout=NamedControl.kr(\timeout,30);
  var life=EnvGen.kr(Env([1,1,0],[timeout.clip(1,30),0]),doneAction:2), noise=PinkNoise.ar(1), sine=SinOsc.ar(1000), side=ToggleFF.kr(Impulse.kr(1));
  var mono=SelectX.ar(kind.clip(0,2),[noise,sine,SinOsc.ar(1000)]), signal=[mono,mono];
  signal=SelectX.ar((kind>1).clip(0,1),[signal,[mono*(1-side),mono*side]]);
  8.do { |g| Out.ar(52+(2*g),signal * level.clip(0,0.031623) * life * InRange.kr(destination,g-0.01,g+0.01)) };
}).writeDefFile("/payload-out");

SynthDef(\sc_adat_quad_master, {
  var rawInputs = In.ar(26, 16), groupStems = In.ar(52, 16), groupMeter = Array.fill(8, { |g| groupStems[g * 2] + groupStems[g * 2 + 1] }), g0 = In.ar(76, 4), g1 = In.ar(80, 4), g2 = In.ar(84, 4), g3 = In.ar(88, 4), g4 = In.ar(92, 4), g5 = In.ar(96, 4), g6 = In.ar(100, 4), g7 = In.ar(104, 4);
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
  SendReply.kr(Impulse.kr(10), "/mixer/meter", rawInputs.collect { |x| Amplitude.kr(x, 0.01, 0.1) } ++ rawInputs.collect { |x| Lag.kr(A2K.kr(x.squared), 0.1).sqrt } ++ groupMeter.collect { |x| Amplitude.kr(x, 0.01, 0.1) } ++ groupMeter.collect { |x| Lag.kr(A2K.kr(x.squared), 0.1).sqrt } ++ output.collect { |x| Amplitude.kr(x, 0.01, 0.1) } ++ Array.fill(12, { 0 }) ++ output.collect { |x| Lag.kr(A2K.kr(x.squared), 0.1).sqrt } ++ Array.fill(12, { 0 }));
}).writeDefFile("/payload-out");

SynthDef(\sc_adat_stereo_master, {
  var rawInputs = In.ar(26, 16), groupStems = In.ar(52, 16), groupMeter = Array.fill(8, { |g| groupStems[g * 2] + groupStems[g * 2 + 1] }), g0 = In.ar(76, 4), g1 = In.ar(80, 4), g2 = In.ar(84, 4), g3 = In.ar(88, 4), g4 = In.ar(92, 4), g5 = In.ar(96, 4), g6 = In.ar(100, 4), g7 = In.ar(104, 4);
  var left = g0[0] + g0[2] + g1[0] + g1[2] + g2[0] + g2[2] + g3[0] + g3[2] + g4[0] + g4[2] + g5[0] + g5[2] + g6[0] + g6[2] + g7[0] + g7[2];
  var right = g0[1] + g0[3] + g1[1] + g1[3] + g2[1] + g2[3] + g3[1] + g3[3] + g4[1] + g4[3] + g5[1] + g5[3] + g6[1] + g6[3] + g7[1] + g7[3];
  var master = NamedControl.kr(\master, 1), panicMute=NamedControl.kr(\panicMute,0), output, eqBypass=NamedControl.kr(\masterEqBypass,1), eqDb=NamedControl.kr(\masterEqDb,0), smoothing = NamedControl.kr(\smoothing, 0.03);
  master = Lag.kr(master.clip(0, 2), smoothing);
  output = [left, right].collect { |x| var shaped=SelectX.ar(eqBypass.clip(0,1),[BPeakEQ.ar(x,1000,0.5,eqDb.clip(-6,6)),x]); Limiter.ar((shaped * master).clip2(4), 0.99, 0.01) * (1-panicMute.clip(0,1)) };
  Out.ar(0, output);
  SendReply.kr(Impulse.kr(10), "/mixer/meter", rawInputs.collect { |x| Amplitude.kr(x, 0.01, 0.1) } ++ rawInputs.collect { |x| Lag.kr(A2K.kr(x.squared), 0.1).sqrt } ++ groupMeter.collect { |x| Amplitude.kr(x, 0.01, 0.1) } ++ groupMeter.collect { |x| Lag.kr(A2K.kr(x.squared), 0.1).sqrt } ++ output.collect { |x| Amplitude.kr(x, 0.01, 0.1) } ++ Array.fill(14, { 0 }) ++ output.collect { |x| Lag.kr(A2K.kr(x.squared), 0.1).sqrt } ++ Array.fill(14, { 0 }));
}).writeDefFile("/payload-out");

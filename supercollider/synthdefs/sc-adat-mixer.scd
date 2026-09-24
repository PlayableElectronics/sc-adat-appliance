// Reusable-node mixer graph. The controller owns node IDs and lifecycle.
// Coordinates use X=-1 left/+1 right and Y=-1 rear/+1 front internally.
SynthDef(\sc_adat_router, {
  var inputs = In.ar(26, 16), trim, mute, polarity, hpf, hpfHz, groupSelect, levels, channels;
  trim = Array.fill(16, { |i| NamedControl.kr(("trim" ++ i).asSymbol, 1) });
  mute = Array.fill(16, { |i| NamedControl.kr(("mute" ++ i).asSymbol, 0) });
  polarity = Array.fill(16, { |i| NamedControl.kr(("polarity" ++ i).asSymbol, 1) });
  hpf = Array.fill(16, { |i| NamedControl.kr(("hpf" ++ i).asSymbol, 0) });
  hpfHz = Array.fill(16, { |i| NamedControl.kr(("hpfHz" ++ i).asSymbol, 80) });
  groupSelect = Array.fill(16, { |i| NamedControl.kr(("groupSelect" ++ i).asSymbol, ((i div: 2) min: 7)) });
  levels = Array.fill(8, { |i| NamedControl.kr(("level" ++ i).asSymbol, 1) });
  trim = trim.collect { |x| Lag.kr(x.clip(0.0001, 4), 0.03) }; mute = mute.collect { |x| Lag.kr(x.clip(0, 1), 0.03) }; polarity = polarity.collect { |x| Lag.kr(x.clip(-1, 1), 0.03) }; hpf = hpf.collect { |x| Lag.kr(x.clip(0, 1), 0.03) }; hpfHz = hpfHz.collect { |x| Lag.kr(x.clip(20, 20000), 0.03) }; levels = levels.collect { |x| Lag.kr(x.clip(0, 2), 0.03) };
  channels = inputs.collect { |sig, i| var filtered = SelectX.ar(hpf[i], [sig, HPF.ar(sig, hpfHz[i])]); filtered * trim[i] * (1 - mute[i]) * polarity[i] };
  Out.ar(60, channels.collect { |sig, i| sig * Select.kr(groupSelect[i].clip(0, 7), levels) });
  8.do { |g| Out.ar(52 + g, Mix(channels.collect { |sig, i| sig * InRange.kr(groupSelect[i], g - 0.01, g + 0.01) })) };
  SendReply.kr(Impulse.kr(10), "/mixer/router-meter", channels.collect { |x| Amplitude.kr(x, 0.01, 0.1) } ++ channels.collect { |x| Lag.kr(A2K.kr(x.squared), 0.1).sqrt });
}).writeDefFile("/payload-out");

SynthDef(\sc_adat_group, { |inbus=52, outbus=64|
  var sig = In.ar(inbus, 1), gain = NamedControl.kr(\gain, 1), mute = NamedControl.kr(\mute, 0);
  var x = NamedControl.kr(\x, 0), y = NamedControl.kr(\y, 1), width = NamedControl.kr(\width, 0);
  var spatialBypass = NamedControl.kr(\spatialBypass, 0), xMin = NamedControl.kr(\xMin, -1), xMax = NamedControl.kr(\xMax, 1);
  var yMin = NamedControl.kr(\yMin, -1), yMax = NamedControl.kr(\yMax, 1), widthMin = NamedControl.kr(\widthMin, 0), widthMax = NamedControl.kr(\widthMax, 1);
  var neutralX = NamedControl.kr(\neutralX, 0), neutralY = NamedControl.kr(\neutralY, 1), neutralWidth = NamedControl.kr(\neutralWidth, 0);
  var pan, sx, sy, sw, left, right, gains, neutral, norm, neutralNorm;
  pan = { |px, py| var xx = ((px + 1) * 0.5).clip(0, 1); var yy = ((py + 1) * 0.5).clip(0, 1); [((1-xx)*(1-yy)).sqrt, (xx*(1-yy)).sqrt, ((1-xx)*yy).sqrt, (xx*yy).sqrt] };
  gain = Lag.kr(gain.clip(0.0001, 2), 0.03); mute = Lag.kr(mute.clip(0, 1), 0.03); x = Lag.kr(x.clip(xMin, xMax), 0.03); y = Lag.kr(y.clip(yMin, yMax), 0.03); width = Lag.kr(width.clip(widthMin, widthMax), 0.03); spatialBypass = Lag.kr(spatialBypass.clip(0, 1), 0.03);
  sx = x.clip(xMin, xMax); sy = y.clip(yMin, yMax); sw = width.clip(widthMin, widthMax); left = pan.value(sx - sw, sy); right = pan.value(sx + sw, sy); gains = 4.collect { |i| (left[i] + right[i]) * 0.5 }; norm = (gains.collect { |v| v.squared }.sum.sqrt).max(0.0001); gains = gains.collect { |v| v / norm };
  left = pan.value(neutralX - neutralWidth, neutralY); right = pan.value(neutralX + neutralWidth, neutralY); neutral = 4.collect { |i| (left[i] + right[i]) * 0.5 }; neutralNorm = (neutral.collect { |v| v.squared }.sum.sqrt).max(0.0001); neutral = neutral.collect { |v| v / neutralNorm };
  Out.ar(outbus, 4.collect { |i| sig * gain * (1 - mute) * (gains[i] * (1 - spatialBypass) + neutral[i] * spatialBypass) });
}).writeDefFile("/payload-out");

SynthDef(\sc_adat_quad_master, { |directbus=60, groupbus=64, out0=0, out1=1, out2=2, out3=3|
  var direct = In.ar(directbus, 16), rawInputs = In.ar(26, 16), groupStems = In.ar(52, 8), groups = In.ar(groupbus, 32), quad = 4.collect { |i| Mix(groups.copyRange(i * 4, (i * 4) + 3)) };
  var mode = NamedControl.kr(\quadMode, 0), master = NamedControl.kr(\master, 1), bypass = NamedControl.kr(\bypass, 0);
  var gain = Array.fill(4, { |i| NamedControl.kr(("quadOutput" ++ i ++ "Gain").asSymbol, 1) });
  var mute = Array.fill(4, { |i| NamedControl.kr(("quadOutput" ++ i ++ "Mute").asSymbol, 0) });
  var polarity = Array.fill(4, { |i| NamedControl.kr(("quadOutput" ++ i ++ "Polarity").asSymbol, 1) });
  var physical;
  gain = gain.collect { |x| Lag.kr(x.clip(0.0001, 2), 0.03) }; mute = mute.collect { |x| Lag.kr(x.clip(0, 1), 0.03) }; polarity = polarity.collect { |x| Lag.kr(x.clip(-1, 1), 0.03) }; master = Lag.kr(master.clip(0, 2), 0.03); bypass = Lag.kr(bypass.clip(0, 1), 0.03);
  quad = quad.collect { |x, i| x * gain[i] * (1 - mute[i]) * polarity[i] }; physical = Array.fill(16, { |b| quad[0] * InRange.kr(out0, b-0.01, b+0.01) + quad[1] * InRange.kr(out1, b-0.01, b+0.01) + quad[2] * InRange.kr(out2, b-0.01, b+0.01) + quad[3] * InRange.kr(out3, b-0.01, b+0.01) });
  physical = SelectX.ar(mode.clip(0, 1), [direct * master, physical * master]); physical = SelectX.ar(bypass, [physical, rawInputs]); physical = physical.collect { |x| Limiter.ar(x.clip2(4), 0.99, 0.01) }; Out.ar(0, physical);
  SendReply.kr(Impulse.kr(10), "/mixer/meter", rawInputs.collect { |x| Amplitude.kr(x, 0.01, 0.1) } ++ rawInputs.collect { |x| Lag.kr(A2K.kr(x.squared), 0.1).sqrt } ++ groupStems.collect { |x| Amplitude.kr(x, 0.01, 0.1) } ++ groupStems.collect { |x| Lag.kr(A2K.kr(x.squared), 0.1).sqrt } ++ physical.collect { |x| Amplitude.kr(x, 0.01, 0.1) } ++ physical.collect { |x| Lag.kr(A2K.kr(x.squared), 0.1).sqrt });
}).writeDefFile("/payload-out");

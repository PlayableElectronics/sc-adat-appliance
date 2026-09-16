// DSP only. Configuration and OSC policy are implemented by mixerctl.py.
SynthDef(\sc_adat_mixer, {
  var inputs = In.ar(26, 16);
  var trim = Array.fill(16, { |i| NamedControl.kr(("trim" ++ i).asSymbol, 1) });
  var mute = Array.fill(16, { |i| NamedControl.kr(("mute" ++ i).asSymbol, 0) });
  var polarity = Array.fill(16, { |i| NamedControl.kr(("polarity" ++ i).asSymbol, 1) });
  var hpf = Array.fill(16, { |i| NamedControl.kr(("hpf" ++ i).asSymbol, 0) });
  var hpfHz = Array.fill(16, { |i| NamedControl.kr(("hpfHz" ++ i).asSymbol, 80) });
  var groupMix = Array.fill(16, { |i| Array.fill(5, { |g| NamedControl.kr(("group" ++ i ++ "_" ++ g).asSymbol, if(((i div: 4) min: 4) == g, 1, 0)) }) });
  var groupLevel = Array.fill(5, { |g| NamedControl.kr(("groupLevel" ++ g).asSymbol, 1) });
  var master = NamedControl.kr(\master, 1);
  var bypass = NamedControl.kr(\bypass, 0);
  var channels, grouped, outputs;
  trim = trim.collect { |x| Lag.kr(x.clip(0.0001, 4), 0.03) };
  mute = mute.collect { |x| Lag.kr(x.clip(0, 1), 0.03) };
  polarity = polarity.collect { |x| Lag.kr(x.clip(-1, 1), 0.03) };
  hpf = hpf.collect { |x| Lag.kr(x.clip(0, 1), 0.03) };
  hpfHz = hpfHz.collect { |x| Lag.kr(x.clip(20, 20000), 0.03) };
  groupLevel = groupLevel.collect { |x| Lag.kr(x.clip(0, 2), 0.03) };
  master = Lag.kr(master.clip(0, 2), 0.03);
  bypass = Lag.kr(bypass.clip(0, 1), 0.03);
  channels = inputs.collect { |sig, i|
    var filtered = SelectX.ar(hpf[i], [sig, HPF.ar(sig, hpfHz[i])]);
    var groupGain = (groupMix[i] * groupLevel).sum.clip(0, 2);
    (filtered * trim[i] * (1 - mute[i]) * polarity[i] * groupGain).clip2(4)
  };
  grouped = channels;
  outputs = grouped;
  outputs = SelectX.ar(bypass, [outputs * master, inputs]);
  outputs = outputs.collect { |sig| Limiter.ar(sig.clip2(4), 0.99, 0.01) };
  Out.ar(0, outputs);
  SendReply.kr(Impulse.kr(10), "/mixer/meter",
    channels.collect { |x| Amplitude.kr(x, 0.01, 0.1) }
    ++ channels.collect { |x| Lag.kr(A2K.kr(x.squared), 0.1).sqrt }
    ++ [Mix(grouped[0..3]), grouped[4], Mix(grouped[5..8]), Mix(grouped[9..11]), Mix(grouped[12..15])]
      .collect { |x| Amplitude.kr(x, 0.01, 0.1) }
    ++ [Mix(grouped[0..3]), grouped[4], Mix(grouped[5..8]), Mix(grouped[9..11]), Mix(grouped[12..15])]
      .collect { |x| Lag.kr(A2K.kr(x.squared), 0.1).sqrt }
    ++ outputs.collect { |x| Amplitude.kr(x, 0.01, 0.1) }
    ++ outputs.collect { |x| Lag.kr(A2K.kr(x.squared), 0.1).sqrt }
  );
}).writeDefFile("/payload-out");

// Authoritative source. Debian's pinned sclang compiles this file. Buildroot
// consumes only the resulting target-independent .scsyndef files.
SynthDef(\sc_adat_tone24, { |level=(-36), gate=0|
  var freqs = (200, 250 .. 1350);
  var env = EnvGen.kr(Env.asr(0.25, 1, 0.25), gate, doneAction: 2);
  Out.ar(0, freqs.collect { |freq| SinOsc.ar(freq, 0, level.dbamp * env) });
}).writeDefFile("/payload-out");

SynthDef(\sc_adat_scan, { |output=0, freq=200, level=(-36), gate=0|
  var env = EnvGen.kr(Env.asr(0.05, 1, 0.10), gate, doneAction: 2);
  Out.ar(output, SinOsc.ar(freq, 0, level.dbamp * env));
}).writeDefFile("/payload-out");

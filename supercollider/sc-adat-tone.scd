// Source of the deterministic deployed SynthDef. The appliance loads the
// compiled scsyndef through OSC; sclang is never needed on the target.
SynthDef(\sc_adat_tone24, { |level=0, gate=0, f1=200, f2=250, f3=300, f4=350,
  f5=400, f6=450, f7=500, f8=550, f9=600, f10=650, f11=700, f12=750,
  f13=800, f14=850, f15=900, f16=950, f17=1000, f18=1050, f19=1100,
  f20=1150, f21=1200, f22=1250, f23=1300, f24=1350|
  var freqs = [f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13,f14,f15,f16,f17,f18,f19,f20,f21,f22,f23,f24];
  var env = EnvGen.kr(Env.asr(0.25, 1, 0.25), gate, doneAction: 2);
  freqs.do { |freq, i| Out.ar(i, SinOsc.ar(freq, 0, level.dbamp * env)) };
}).writeDefFile;

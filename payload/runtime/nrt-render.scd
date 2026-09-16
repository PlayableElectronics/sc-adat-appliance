var options = ServerOptions.new.numOutputBusChannels_(26).numInputBusChannels_(0).sampleRate_(48000);
var score = Score([
  [0.0, [\d_load, "/payload-out/synthdefs/sc_adat_tone24.scsyndef"]],
  [0.0, [\s_new, \sc_adat_tone24, 1000, 0, 0, \level, -36, \gate, 1]],
  [1.5, [\n_set, 1000, \gate, 0]],
  [2.0, [\c_set, 0, 0]]
]);
score.recordNRT("/payload-out/sc-adat-tone24.osc", "/payload-out/sc-adat-tone24.wav", sampleRate: 48000, headerFormat: "WAV", sampleFormat: "float", options: options, duration: 2.0, action: { "NRT_RENDER_PASS".postln; 0.exit });

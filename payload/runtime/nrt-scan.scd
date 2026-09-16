var options = ServerOptions.new.numOutputBusChannels_(26).numInputBusChannels_(0).sampleRate_(48000);
var score = Score([
  [0.0, [\d_load, "/payload-out/synthdefs/sc_adat_scan.scsyndef"]],
  [0.0, [\s_new, \sc_adat_scan, 1001, 0, 0, \output, 7, \freq, 550, \level, -36, \gate, 1]],
  [1.5, [\n_set, 1001, \gate, 0]],
  [2.0, [\c_set, 0, 0]]
]);
score.recordNRT("/payload-out/sc-adat-scan.osc", "/payload-out/sc-adat-scan.wav", sampleRate: 48000, headerFormat: "WAV", sampleFormat: "float", options: options, duration: 2.0, action: { "NRT_SCAN_PASS".postln; 0.exit });

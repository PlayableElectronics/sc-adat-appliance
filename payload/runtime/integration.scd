// Real scsynth OSC acknowledgement test for the development container.
var server = NetAddr("127.0.0.1", 57120);
var done = Condition.new;
var synced = Condition.new;
OSCFunc({ |msg| if(msg[0] == '/done', { done.unhang }) }, '/done');
OSCFunc({ |msg| if(msg[0] == '/synced', { synced.unhang }) }, '/synced');
Routine({
  server.sendMsg('/d_load', "/payload-out/synthdefs/sc_adat_tone24.scsyndef");
  done.hang;
  server.sendMsg('/sync', 77);
  synced.hang;
  0.exit;
}).play(AppClock);

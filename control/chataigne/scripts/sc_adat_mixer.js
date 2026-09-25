/* SC-ADAT Chataigne 1.10.4 project script.
 * Native dashboard controls live in Custom Variables. This script is the
 * single OSC boundary and snapshots values on load, so opening the project
 * sends no mixer writes. Remote state is applied under remoteUpdate and is
 * not echoed.
 */
var GROUPS = ["kick", "drums", "bass", "music_a", "music_b", "vocals", "fx_a", "fx_b"];
var NEUTRAL = [[0.5, 1.0, 0.0], [0.5, 0.75, 0.0], [0.5, 1.0, 0.0],
               [0.5, 0.5, 0.5], [0.5, 0.5, 0.5], [0.5, 1.0, 0.0],
               [0.5, 0.5, 0.5], [0.5, 0.5, 0.5]];
var remoteUpdate = false;
var last = {};
var calibrationArmed = false;

function controls() { return root.getChild("customVariables").getChild("scAdat").getChild("variables"); }
function c(name) { return controls().getChild(name); }
function sendSet(key, value) { if (!remoteUpdate && local && local.send) local.send("/mixer/set", key, value); }
function refresh() { if (local && local.send) local.send("/mixer/get-all"); }
function setStatus(text, state) { c("statusText").set(text); c("mixerStatus").set(state); }
function snapshot() {
    for (var i = 0; i < GROUPS.length; i++) {
        last["groupLevel" + i] = c("groupLevel" + i).get();
        last["group" + i + "Position"] = c("group" + i + "Position").get();
        last["group" + i + "Width"] = c("group" + i + "Width").get();
        last["group" + i + "SpatialBypass"] = c("group" + i + "SpatialBypass").get();
    }
    last.master = c("master").get(); last.bypass = c("bypass").get();
    for (var n = 0; n < 4; n++) {
        last["quadOutput" + n + "GainDb"] = c("quadOutput" + n + "GainDb").get();
        last["quadOutput" + n + "Mute"] = c("quadOutput" + n + "Mute").get();
        last["quadOutput" + n + "Polarity"] = c("quadOutput" + n + "Polarity").get();
    }
}
function changed(key, value) {
    if (last[key] === undefined || JSON.stringify(last[key]) != JSON.stringify(value)) { last[key] = value; return true; }
    return false;
}
function stopAutomation() {
    var parrots = root.getChild("parrots");
    if (parrots) { var items = parrots.getContainers(); for (var i = 0; i < items.length; i++) { var stop = items[i].getChild("stop"); if (stop && stop.trigger) stop.trigger(); } }
    var sequences = root.getChild("sequences");
    if (sequences) { var all = sequences.getChild("stopAll"); if (all && all.trigger) all.trigger(); }
    c("automationArm").set(false); setStatus("Automation stopped; manual/current values retained", 0);
}
function resetGroup(i) {
    var n = NEUTRAL[i]; remoteUpdate = true;
    c("group" + i + "Position").set([n[0], n[1]]); c("group" + i + "Width").set(n[2]); remoteUpdate = false;
    sendSet("group" + i + "PosX", n[0]); sendSet("group" + i + "PosY", n[1]); sendSet("group" + i + "Width", n[2]);
    c("group" + i + "NeutralReset").set(false);
}
function processUserValues() {
    if (remoteUpdate) return;
    for (var i = 0; i < GROUPS.length; i++) {
        var level = c("groupLevel" + i).get(); if (changed("groupLevel" + i, level)) sendSet("groupLevel" + i, level);
        var pos = c("group" + i + "Position").get();
        if (changed("group" + i + "Position", pos)) { sendSet("group" + i + "PosX", pos[0]); sendSet("group" + i + "PosY", pos[1]); }
        var width = c("group" + i + "Width").get(); if (changed("group" + i + "Width", width)) sendSet("group" + i + "Width", width);
        var bypass = c("group" + i + "SpatialBypass").get(); if (changed("group" + i + "SpatialBypass", bypass)) sendSet("group" + i + "SpatialBypass", bypass ? 1 : 0);
        if (c("group" + i + "NeutralReset").get()) resetGroup(i);
    }
    var master = c("master").get(); if (changed("master", master)) sendSet("master", master);
    var bypassAll = c("bypass").get(); if (changed("bypass", bypassAll)) sendSet("bypass", bypassAll ? 1 : 0);
    for (var n = 0; n < 4; n++) {
        var gain = c("quadOutput" + n + "GainDb").get(), mute = c("quadOutput" + n + "Mute").get(), polarity = c("quadOutput" + n + "Polarity").get();
        if (changed("quadOutput" + n + "GainDb", gain) && calibrationArmed) sendSet("quadOutput" + n + "GainDb", gain);
        if (changed("quadOutput" + n + "Mute", mute) && calibrationArmed) sendSet("quadOutput" + n + "Mute", mute ? 1 : 0);
        if (changed("quadOutput" + n + "Polarity", polarity) && calibrationArmed) sendSet("quadOutput" + n + "Polarity", polarity);
    }
}
function init() { snapshot(); setStatus("Waiting for explicit Refresh", 1); }
function update() {
    if (c("connectRefresh").get()) { c("connectRefresh").set(false); refresh(); setStatus("Waiting for mixer state", 1); }
    if (c("stopAutomation").get()) { c("stopAutomation").set(false); stopAutomation(); }
    calibrationArmed = c("calibrationArm").get(); processUserValues();
}
function setRemote(key, value) {
    if (key == "master" || key == "bypass") { c(key).set(value); return; }
    var match = /^groupLevel([0-7])$/.exec(key); if (match) { c("groupLevel" + match[1]).set(value); return; }
    match = /^group([0-7])Pos([XY])$/.exec(key);
    if (match) { var p = c("group" + match[1] + "Position").get(); p[match[2] == "X" ? 0 : 1] = value; c("group" + match[1] + "Position").set(p); return; }
    match = /^group([0-7])(Width|SpatialBypass)$/.exec(key); if (match) { c("group" + match[1] + match[2]).set(value); return; }
    if (/^quadOutput[0-3](GainDb|Mute|Polarity)$/.test(key)) c(key).set(value);
}
function oscEvent(address, args) {
    if (address == "/mixer/state" && args.length >= 2) { remoteUpdate = true; setRemote(String(args[0]), args[1]); snapshot(); remoteUpdate = false; setStatus("Mixer state current", 0); }
    else if (address == "/mixer/ok" || address == "/mixer/get-all-done") setStatus("Mixer connected/current", 0);
    else if (address == "/mixer/error") setStatus("Mixer error: " + String(args[0]), 2);
}

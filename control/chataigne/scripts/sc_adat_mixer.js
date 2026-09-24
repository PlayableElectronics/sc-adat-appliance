/*
  SC-ADAT OSC helper for Chataigne 1.10.4.

  Attach this readable script to the seed-derived OSC module. It deliberately
  sends only the established /mixer contract and never sends on load.
*/
var GROUPS = ["kick", "drums", "bass", "music_a", "music_b", "vocals", "fx_a", "fx_b"];
var automationArmed = false;
var stale = true;
var lastError = "";

function sendSet(key, value) {
    if (typeof local == "undefined" || !local.send) return;
    local.send("/mixer/set", key, value);
}

function refresh() {
    if (typeof local != "undefined" && local.send) local.send("/mixer/get-all");
}

function stopAutomation() {
    automationArmed = false;
    script.log("Automation stopped; manual/current mixer values retained");
}

function armAutomation() {
    automationArmed = true;
    script.log("Automation armed explicitly");
}

function scriptParameterChanged(param) {
    if (param.name == "Connect / Refresh") { refresh(); return; }
    if (param.name == "Stop Automation") { stopAutomation(); return; }
    if (param.name == "Arm Automation") { armAutomation(); return; }
    // The OSC module exposes the seed-format /scadat/* controls. Their
    // parameter names are the established mixer keys, so only a user change
    // becomes a /mixer/set packet; loading or connecting does not.
    var key = String(param.name);
    if (key.indexOf("group") == 0 || key.indexOf("quadOutput") == 0 ||
        key == "master" || key == "bypass" || key == "routingMode") {
        sendSet(key, param.get());
    }
}

function oscEvent(address, args) {
    if (address == "/mixer/state") {
        stale = false;
        script.log("Mixer state: " + args[0] + " = " + args[1]);
    } else if (address == "/mixer/ok") {
        stale = false;
    } else if (address == "/mixer/error") {
        lastError = String(args[0]);
        stale = true;
        script.log("Mixer error: " + lastError);
    } else if (address == "/mixer/get-all-done") {
        stale = false;
    }
}

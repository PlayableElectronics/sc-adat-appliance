-- SC-ADAT external mixer controller for norns.
-- Audio remains on the Dell; norns only exchanges OSC control messages.

local util = require "util"
local contract = include("lib/mixer_contract")

local DELL = {"192.168.1.136", 57120}
local REPLY_PORT = 10111
local QUERY_PAUSE = 0.015
local MAX_SYNC_ATTEMPTS = 3
local METER_PERIOD = 0.1

local by_key = {}
local received = {}
local received_count = 0
local expected_count = #contract.controls + 1 -- plus controlContractVersion
local applying_remote = false
local ready = false
local status = "starting"
local sync_clock = nil
local meter_clock = nil
local selected_strip = 1
local group_peaks = {0, 0, 0, 0, 0, 0, 0, 0}
local group_rms = {0, 0, 0, 0, 0, 0, 0, 0}
local output_peaks = {0, 0}

local strip_labels = {"K", "DR", "BS", "A", "B", "VO", "F1", "F2", "M"}

local function amp_to_db(value)
  if value <= 0 then return -120 end
  return 20 * math.log(value) / math.log(10)
end

local function db_to_amp(value)
  if value <= -120 then return 0 end
  return 10 ^ (value / 20)
end

local function nearest_index(values, value)
  local winner = 1
  local distance = math.huge
  for index, candidate in ipairs(values) do
    local current = math.abs(candidate - value)
    if current < distance then
      winner = index
      distance = current
    end
  end
  return winner
end

local function wire_value(definition, value)
  if definition.kind == "db" then return db_to_amp(value) end
  if definition.kind == "boolean" then return value end
  if definition.kind == "enum" or (definition.kind == "frequency" and definition.values ~= nil) then
    return definition.values[value]
  end
  return value
end

local function local_value(definition, value)
  value = tonumber(value)
  if value == nil then return nil end
  if definition.kind == "db" then return amp_to_db(value) end
  if definition.kind == "boolean" then return value >= 0.5 and 1 or 0 end
  if definition.kind == "enum" or (definition.kind == "frequency" and definition.values ~= nil) then
    return nearest_index(definition.values, value)
  end
  return value
end

local function send_set(definition, value)
  if not ready or applying_remote then return end
  osc.send(DELL, "/mixer/set", {definition.key, wire_value(definition, value), REPLY_PORT})
  status = "setting " .. definition.key
  redraw()
end

local function add_parameter(definition)
  local id = definition.key
  if definition.kind == "db" then
    params:add_control(
      id,
      definition.label,
      controlspec.new(definition.min, definition.max, "lin", definition.step, definition.min, "dB")
    )
  elseif definition.kind == "boolean" then
    params:add_binary(id, definition.label, "toggle", 0)
  elseif definition.kind == "enum" then
    local labels = {}
    for _, value in ipairs(definition.values) do
      if string.match(definition.key, "Group$") then
        local groups = {"KICK", "DRUMS", "BASS", "MUSIC A", "MUSIC B", "VOCALS", "FX A", "FX B"}
        table.insert(labels, groups[value + 1] or tostring(value))
      elseif string.match(definition.key, "Partner$") then
        table.insert(labels, value == 0 and "MONO" or ("INPUT " .. tostring(value)))
      elseif string.match(definition.key, "Mode$") then
        table.insert(labels, value == 0 and "MONO" or "STEREO")
      elseif string.match(definition.key, "Orientation$") then
        table.insert(labels, ({[0] = "MONO", [1] = "LEFT", [2] = "RIGHT"})[value] or tostring(value))
      elseif value == 1 then table.insert(labels, "NORMAL")
      elseif value == -1 then table.insert(labels, "INVERTED")
      else table.insert(labels, tostring(value)) end
    end
    params:add_option(id, definition.label, labels, 1)
  elseif definition.kind == "frequency" then
    if definition.values ~= nil then
      local labels = {}
      for _, value in ipairs(definition.values) do table.insert(labels, tostring(value) .. " Hz") end
      params:add_option(id, definition.label, labels, 1)
    else
      params:add_control(
        id,
        definition.label,
        controlspec.new(definition.min, definition.max, "exp", definition.step, definition.min, "Hz")
      )
    end
  elseif definition.kind == "normalized" then
    params:add_control(
      id,
      definition.label,
      controlspec.new(definition.min, definition.max, "lin", definition.step, 0)
    )
  end
  if definition.writable ~= false then
    params:set_action(id, function(value) send_set(definition, value) end)
  end
end

local function mark_received(key)
  if not received[key] then
    received[key] = true
    received_count = received_count + 1
  end
end

local function accept_state(key, value)
  if key == "controlContractVersion" then
    mark_received(key)
    if tostring(value) ~= contract.version then
      ready = false
      status = "CONTRACT MISMATCH"
    end
    return
  end

  local definition = by_key[key]
  if definition == nil then return end
  local converted = local_value(definition, value)
  if converted == nil then return end

  applying_remote = true
  params:set(key, converted)
  applying_remote = false
  mark_received(key)
end

local function query(key)
  osc.send(DELL, "/mixer/get", {key, REPLY_PORT})
end

local function synchronize()
  if sync_clock ~= nil then clock.cancel(sync_clock) end
  ready = false
  received = {}
  received_count = 0
  status = "syncing"
  redraw()

  sync_clock = clock.run(function()
    for attempt = 1, MAX_SYNC_ATTEMPTS do
      query("controlContractVersion")
      clock.sleep(QUERY_PAUSE)
      for _, definition in ipairs(contract.controls) do
        if not received[definition.key] then
          query(definition.key)
          clock.sleep(QUERY_PAUSE)
        end
      end
      clock.sleep(0.25)
      if received_count == expected_count then break end
      status = "retry " .. attempt
      redraw()
    end

    if received_count == expected_count and status ~= "CONTRACT MISMATCH" then
      ready = true
      status = "connected"
    elseif status ~= "CONTRACT MISMATCH" then
      status = "sync " .. received_count .. "/" .. expected_count
    end
    sync_clock = nil
    redraw()
  end)
end

local function meter_height(amplitude)
  amplitude = tonumber(amplitude) or 0
  if amplitude ~= amplitude or amplitude == math.huge or amplitude == -math.huge then return 0 end
  if amplitude <= 0 then return 0 end
  local db = amp_to_db(amplitude)
  return util.clamp(util.round(util.linlin(-60, 0, 0, 43, db)), 0, 43)
end

local function level_height(key)
  local db = tonumber(params:get(key)) or -120
  return util.clamp(util.round(util.linlin(-60, 6, 0, 43, db)), 0, 43)
end

local function request_meters()
  osc.send(DELL, "/mixer/meters", {REPLY_PORT})
end

local function start_metering()
  if meter_clock ~= nil then clock.cancel(meter_clock) end
  meter_clock = clock.run(function()
    while true do
      if ready then request_meters() end
      clock.sleep(METER_PERIOD)
    end
  end)
end

local function accept_meters(args)
  if #args < 80 then return end
  for index = 1, 8 do
    group_peaks[index] = tonumber(args[32 + index]) or 0
    group_rms[index] = tonumber(args[40 + index]) or 0
  end
  output_peaks[1] = tonumber(args[49]) or 0
  output_peaks[2] = tonumber(args[50]) or 0
end

function init()
  for _, definition in ipairs(contract.controls) do by_key[definition.key] = definition end

  params:add_group("sc_adat_connection", "SC-ADAT", 1)
  params:add_trigger("sc_adat_sync", "Sync from Dell")
  params:set_action("sc_adat_sync", synchronize)

  for index, page in ipairs(contract.pages) do
    params:add_group("sc_adat_page_" .. index, page.label, #page.controls)
    for _, key in ipairs(page.controls) do add_parameter(by_key[key]) end
  end

  synchronize()
  start_metering()
end

function osc.event(path, args, from)
  if from[1] ~= DELL[1] then return end
  if path == "/mixer/state" and #args >= 2 then
    accept_state(tostring(args[1]), args[2])
    redraw()
  elseif path == "/mixer/ok" then
    status = "connected"
    redraw()
  elseif path == "/mixer/error" then
    status = "ERROR: " .. tostring(args[1] or "unknown")
    redraw()
  elseif path == "/mixer/meters" then
    accept_meters(args)
    redraw()
  end
end

function enc(number, delta)
  if number == 1 then
    selected_strip = util.clamp(selected_strip + delta, 1, 9)
  elseif number == 2 and ready then
    if selected_strip <= 8 then
      params:delta("groupLevel" .. (selected_strip - 1), delta)
    else
      params:delta("master", delta)
    end
  elseif number == 3 and ready then
    params:delta("master", delta)
  end
  redraw()
end

function key(number, pressed)
  if pressed ~= 1 then return end
  if number == 2 then
    selected_strip = util.clamp(selected_strip - 1, 1, 9)
    redraw()
  elseif number == 3 then
    selected_strip = util.clamp(selected_strip + 1, 1, 9)
    redraw()
  end
end

function redraw()
  screen.clear()
  screen.aa(1)
  screen.line_width(1)

  for strip = 1, 9 do
    local x = 2 + (strip - 1) * 14
    local key = strip <= 8 and ("groupLevel" .. (strip - 1)) or "master"
    local target = level_height(key)
    local peak
    local rms
    if strip <= 8 then
      peak = meter_height(group_peaks[strip])
      rms = meter_height(group_rms[strip])
    else
      peak = math.max(meter_height(output_peaks[1]), meter_height(output_peaks[2]))
      rms = 0
    end

    -- Same visual language as norns' global MIX page: a dim target-level
    -- rail beside brighter live level bars.
    screen.level(2)
    screen.rect(x + 0.5, 51.5, 2, -target)
    screen.stroke()

    screen.level(7)
    screen.rect(x + 5, 51, 2, -rms)
    screen.fill()

    screen.level(15)
    screen.rect(x + 8, 51, 2, -peak)
    screen.fill()

    screen.level(selected_strip == strip and 15 or 3)
    screen.move(x, 63)
    screen.text(strip_labels[strip])
  end

  screen.level(ready and 7 or 15)
  screen.move(1, 7)
  if ready then
    local selected_key = selected_strip <= 8 and ("groupLevel" .. (selected_strip - 1)) or "master"
    screen.text(strip_labels[selected_strip] .. "  " .. params:string(selected_key))
  else
    screen.text(status)
  end
  screen.update()
end

function cleanup()
  if sync_clock ~= nil then clock.cancel(sync_clock) end
  if meter_clock ~= nil then clock.cancel(meter_clock) end
end

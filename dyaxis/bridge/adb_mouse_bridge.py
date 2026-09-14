#!/usr/bin/env python3
"""Expose the ADB Kensington trackball as a Linux uinput mouse.

The Uno runs ADBHostProbe and emits lines such as:
    D3R0 2: 81 7F

Classic ADB mouse packets use the high bit of each byte for button state and
the lower seven bits for signed motion.  Linux's ADB driver maps byte 2 to X
and byte 1 to Y, which is followed here.
"""

import os
import re
import sys
import time
from glob import glob
import serial
from evdev import UInput, ecodes

PORT = os.environ.get("DYAXIS_SERIAL", "/dev/ttyUSB0")
PACKET = re.compile(r"^D3R0\s+2:\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})")
KEYPACKET = re.compile(r"^K2R0\s+(\d+):((?:\s+[0-9A-Fa-f]{2})+)")
KEYSTATUS = re.compile(r"^K2R3\s+2:\s+[0-9A-Fa-f]{2}\s+[0-9A-Fa-f]{2}")

# Standard Apple ADB keyboard scan codes. This covers the ANSI layout and
# the complete main section plus navigation/function keys used by the Dyaxis.
KEYMAP = {
    0x00:'KEY_A',0x01:'KEY_S',0x02:'KEY_D',0x03:'KEY_F',0x04:'KEY_H',0x05:'KEY_G',
    0x06:'KEY_Z',0x07:'KEY_X',0x08:'KEY_C',0x09:'KEY_V',0x0B:'KEY_B',0x0C:'KEY_Q',
    0x0D:'KEY_W',0x0E:'KEY_E',0x0F:'KEY_R',0x10:'KEY_Y',0x11:'KEY_T',0x12:'KEY_1',
    0x13:'KEY_2',0x14:'KEY_3',0x15:'KEY_4',0x16:'KEY_6',0x17:'KEY_5',0x18:'KEY_EQUAL',
    0x19:'KEY_9',0x1A:'KEY_7',0x1B:'KEY_MINUS',0x1C:'KEY_8',0x1D:'KEY_0',
    0x1E:'KEY_RIGHTBRACE',0x1F:'KEY_O',0x20:'KEY_U',0x21:'KEY_LEFTBRACE',0x22:'KEY_I',
    0x23:'KEY_P',0x24:'KEY_ENTER',0x25:'KEY_L',0x26:'KEY_J',0x27:'KEY_APOSTROPHE',
    0x28:'KEY_K',0x29:'KEY_SEMICOLON',0x2A:'KEY_BACKSLASH',0x2B:'KEY_COMMA',
    0x2C:'KEY_SLASH',0x2D:'KEY_N',0x2E:'KEY_M',0x2F:'KEY_DOT',0x30:'KEY_TAB',
    0x31:'KEY_SPACE',0x32:'KEY_GRAVE',0x33:'KEY_BACKSPACE',0x34:'KEY_KPENTER',
    0x35:'KEY_ESC',0x36:'KEY_LEFTCTRL',0x37:'KEY_LEFTMETA',0x38:'KEY_LEFTSHIFT',
    0x39:'KEY_CAPSLOCK',0x3A:'KEY_LEFTALT',0x3B:'KEY_LEFT',0x3C:'KEY_RIGHT',
    0x3D:'KEY_DOWN',0x3E:'KEY_UP',0x41:'KEY_KPDOT',0x43:'KEY_KPASTERISK',
    0x45:'KEY_KPPLUS',0x47:'KEY_NUMLOCK',0x4B:'KEY_KPSLASH',0x4C:'KEY_KPENTER',
    0x4E:'KEY_KPMINUS',0x51:'KEY_KPEQUAL',0x52:'KEY_KP0',0x53:'KEY_KP1',
    0x54:'KEY_KP2',0x55:'KEY_KP3',0x56:'KEY_KP4',0x57:'KEY_KP5',0x58:'KEY_KP6',
    0x59:'KEY_KP7',0x5B:'KEY_KP8',0x5C:'KEY_KP9',0x60:'KEY_F5',0x61:'KEY_F6',
    0x62:'KEY_F7',0x63:'KEY_F3',0x64:'KEY_F8',0x65:'KEY_F9',0x6B:'KEY_SCROLLLOCK',
    0x6D:'KEY_F10',0x6F:'KEY_F12',0x71:'KEY_PAUSE',0x72:'KEY_INSERT',0x73:'KEY_HOME',
    0x74:'KEY_PAGEUP',0x75:'KEY_DELETE',0x76:'KEY_F4',0x77:'KEY_END',0x78:'KEY_F2',
    0x79:'KEY_PAGEDOWN',0x7A:'KEY_F1',0x7B:'KEY_RIGHTSHIFT',0x7C:'KEY_RIGHTALT',
    0x7D:'KEY_RIGHTCTRL',0x7E:'KEY_RIGHTMETA',0x7F:'KEY_POWER',
}


def signed7(value: int) -> int:
    value &= 0x7F
    return value if value < 64 else value - 128


def main() -> None:
    serial_port = serial.Serial()
    serial_port.port = PORT
    serial_port.baudrate = 115200
    serial_port.timeout = 0.02
    # Opening the CH340 with DTR asserted can reset the Uno. Keep the probe
    # running continuously so the bridge does not lose the ADB state.
    serial_port.dtr = False
    serial_port.rts = False
    serial_port.open()

    capabilities = {
        ecodes.EV_REL: (ecodes.REL_X, ecodes.REL_Y),
        ecodes.EV_KEY: (ecodes.BTN_LEFT, ecodes.BTN_RIGHT),
    }
    mouse = UInput(
        capabilities,
        name="Studer Dyaxis Kensington ADB Trackball",
        vendor=0x1209,
        product=0xADB3,
        version=1,
    )
    key_caps = [getattr(ecodes, name) for name in KEYMAP.values()]
    keyboard = UInput(
        {
            ecodes.EV_KEY: sorted(set(key_caps)),
            ecodes.EV_LED: (ecodes.LED_NUML, ecodes.LED_CAPSL, ecodes.LED_SCROLLL),
        },
        name="Studer Dyaxis ADB Keyboard",
        vendor=0x1209,
        product=0xADB2,
        version=1,
    )

    left = None
    right = None
    last_caps_event = 0.0
    led_mask = 0
    pressed = {}
    repeat_next = {}
    repeat_started = {}
    repeatable = set(KEYMAP) - {0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x7B, 0x7C, 0x7D, 0x7E}

    # Seed the physical LEDs from Linux's existing keyboard state. The virtual
    # keyboard may be recreated on every service restart, but lock state is
    # owned by Linux/the desktop session, not by this process.
    for led_name, bit in (("numlock", 0x01), ("capslock", 0x02), ("scrolllock", 0x04)):
        paths = glob(f"/sys/class/leds/input*::{led_name}/brightness")
        if any(open(path, encoding="ascii").read().strip() == "1" for path in paths):
            led_mask |= bit

    # Deterministic controller startup: Caps Lock begins off and Num Lock on,
    # so the Apple keypad produces digits immediately. Toggle Linux if it
    # retained different lock state across a service restart.
    if led_mask & 0x02:
        keyboard.write(ecodes.EV_KEY, ecodes.KEY_CAPSLOCK, 1)
        keyboard.syn()
        keyboard.write(ecodes.EV_KEY, ecodes.KEY_CAPSLOCK, 0)
        keyboard.syn()
    if not (led_mask & 0x01):
        keyboard.write(ecodes.EV_KEY, ecodes.KEY_NUMLOCK, 1)
        keyboard.syn()
        keyboard.write(ecodes.EV_KEY, ecodes.KEY_NUMLOCK, 0)
        keyboard.syn()
    led_mask &= ~0x02
    led_mask |= 0x01

    def write_leds(mask):
        serial_port.write(f"L {mask}\n".encode())

    write_leds(led_mask)
    startup_led_pending = True
    print(f"dyaxis-adb-mouse: {PORT} -> {mouse.device.name}", flush=True)
    try:
        while True:
            line = serial_port.readline().decode("ascii", errors="ignore")
            # The first command can race the keyboard's ADB reset. A valid
            # register-3 reply proves it is ready, so apply startup state again.
            if startup_led_pending and KEYSTATUS.search(line):
                write_leds(led_mask)
                startup_led_pending = False
            # Output events sent by Linux to the virtual keyboard are the
            # authoritative lock-LED state.
            if keyboard.device is not None:
                while True:
                    event = keyboard.device.read_one()
                    if event is None:
                        break
                    if event.type != ecodes.EV_LED:
                        continue
                    bit = {
                        ecodes.LED_NUML: 0x01,
                        ecodes.LED_CAPSL: 0x02,
                        ecodes.LED_SCROLLL: 0x04,
                    }.get(event.code)
                    if bit is None:
                        continue
                    if event.value:
                        led_mask |= bit
                    else:
                        led_mask &= ~bit
                    write_leds(led_mask)
            now = time.monotonic()
            for code, key in list(pressed.items()):
                # ADB is not error-correcting; if a release packet is lost,
                # never allow a synthetic repeat to run forever.
                if now - repeat_started.get(code, now) >= 5.0:
                    keyboard.write(ecodes.EV_KEY, key, 0)
                    keyboard.syn()
                    pressed.pop(code, None)
                    repeat_next.pop(code, None)
                    repeat_started.pop(code, None)
                    continue
                due = repeat_next.get(code, now + 0.5)
                if now >= due:
                    # EV_KEY value 2 is autorepeat; value 1 is only key-down.
                    keyboard.write(ecodes.EV_KEY, key, 2)
                    keyboard.syn()
                    repeat_next[code] = now + 0.05
            match = PACKET.search(line)
            keymatch = KEYPACKET.search(line)
            if keymatch:
                for token in keymatch.group(2).split():
                    raw = int(token, 16)
                    code = raw & 0x7F
                    name = KEYMAP.get(code)
                    if not name:
                        continue
                    key = getattr(ecodes, name)
                    down = not bool(raw & 0x80)
                    if code == 0x39:
                        # ADB Caps Lock reports alternating edges. Linux needs
                        # a complete momentary tap for either physical edge.
                        now = time.monotonic()
                        if now - last_caps_event >= 0.1:
                            last_caps_event = now
                            keyboard.write(ecodes.EV_KEY, key, 1)
                            keyboard.syn()
                            keyboard.write(ecodes.EV_KEY, key, 0)
                            keyboard.syn()
                            led_mask ^= 0x02
                            write_leds(led_mask)
                        continue
                    keyboard.write(ecodes.EV_KEY, key, int(down))
                    keyboard.syn()
                    if down and code in repeatable:
                        # Only the most recently pressed printable key repeats.
                        # This also clears a stale repeat after a lost release.
                        for old_code, old_key in list(pressed.items()):
                            if old_code != code:
                                keyboard.write(ecodes.EV_KEY, old_key, 0)
                        pressed.clear()
                        repeat_next.clear()
                        repeat_started.clear()
                        keyboard.syn()
                        pressed[code] = key
                        repeat_next.setdefault(code, time.monotonic() + 0.5)
                        repeat_started[code] = time.monotonic()
                    elif not down:
                        pressed.pop(code, None)
                        repeat_next.pop(code, None)
                        repeat_started.pop(code, None)
                continue
            if not match:
                continue
            first, second = (int(match.group(i), 16) for i in (1, 2))

            # ADB button bits are active-low: 0 means pressed.
            new_left = not bool(first & 0x80)
            new_right = not bool(second & 0x80)
            dx = signed7(second)
            dy = signed7(first)

            changed = False
            if dx:
                mouse.write(ecodes.EV_REL, ecodes.REL_X, dx)
                changed = True
            if dy:
                mouse.write(ecodes.EV_REL, ecodes.REL_Y, dy)
                changed = True
            if new_left != left:
                mouse.write(ecodes.EV_KEY, ecodes.BTN_LEFT, int(new_left))
                left = new_left
                changed = True
            if new_right != right:
                mouse.write(ecodes.EV_KEY, ecodes.BTN_RIGHT, int(new_right))
                right = new_right
                changed = True
            if changed:
                mouse.syn()
    finally:
        mouse.close()
        keyboard.close()
        serial_port.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)

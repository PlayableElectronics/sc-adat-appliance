// Minimal ADB host probe for an Arduino Uno.
// DATA is on D2/PD2.  The external 4.7k pull-up is required.
// The PSW line is intentionally unused.

#include <Arduino.h>
#include <util/delay.h>

static const uint8_t DATA_BIT = 2; // PORTD bit 2 / Arduino D2

static inline void data_low() {
  PORTD &= ~(1 << DATA_BIT);
  DDRD |= (1 << DATA_BIT);
}

static inline void data_release() {
  PORTD &= ~(1 << DATA_BIT); // no internal pull-up
  DDRD &= ~(1 << DATA_BIT);
}

static inline bool data_is_high() {
  return (PIND & (1 << DATA_BIT)) != 0;
}

static uint16_t wait_data_low(uint16_t us) {
  while (us--) {
    if (!data_is_high()) return us;
    _delay_us(1);
  }
  return 0;
}

static uint16_t wait_data_high(uint16_t us) {
  while (us--) {
    if (data_is_high()) return us;
    _delay_us(1);
  }
  return 0;
}

static void bit_zero() {
  data_low();
  _delay_us(65);
  data_release();
  _delay_us(35);
}

static void bit_one() {
  data_low();
  _delay_us(35);
  data_release();
  _delay_us(65);
}

static void send_byte(uint8_t value) {
  for (uint8_t i = 0; i < 8; ++i) {
    if (value & (0x80 >> i)) bit_one();
    else bit_zero();
  }
}

static void attention() {
  data_low();
  _delay_us(765);
  bit_one();
}

static void stop_bit() { bit_zero(); }

// Send a LISTEN transaction. ADB keyboard LED state is written to register 2.
static void adb_listen(uint8_t addr, uint8_t reg, const uint8_t *data,
                       uint8_t len) {
  noInterrupts();
  attention();
  send_byte((addr << 4) | 0x08 | (reg & 3)); // LISTEN
  stop_bit();
  // A LISTEN data packet has its own start bit after the stop-to-start
  // interval, continuous data bytes, and one final stop bit.
  _delay_us(200);
  bit_one();
  for (uint8_t i = 0; i < len; ++i) send_byte(data[i]);
  stop_bit();
  interrupts();
  _delay_us(200);
}

static void adb_reset() {
  data_low();
  _delay_us(3000);
  data_release();
  delay(20);
}

// Talk to addr/register. Returns number of response bytes (up to maxlen).
static uint8_t adb_talk(uint8_t addr, uint8_t reg, uint8_t *buf, uint8_t maxlen) {
  for (uint8_t i = 0; i < maxlen; ++i) buf[i] = 0;

  noInterrupts();
  attention();
  send_byte((addr << 4) | 0x0C | (reg & 3)); // TALK
  stop_bit();

  // Device turnaround, then its start bit.
  if (!wait_data_high(500) || !wait_data_low(500)) {
    interrupts();
    return 0;
  }
  if (!wait_data_high(40) || !wait_data_low(100)) {
    interrupts();
    return 0;
  }

  uint8_t bits = 0;
  while (bits < (uint8_t)(maxlen * 8)) {
    uint16_t lo = wait_data_high(130);
    if (!lo) break;
    uint16_t hi = wait_data_low(lo);
    if (!hi) break;
    uint8_t byte = bits / 8;
    buf[byte] <<= 1;
    if ((130 - lo) < (lo - hi)) buf[byte] |= 1;
    ++bits;
  }
  interrupts();
  _delay_us(200);
  return bits / 8;
}

static void print_packet(const char *tag, uint8_t addr, uint8_t reg,
                         const uint8_t *buf, uint8_t len) {
  // Keep output short: ADB transactions briefly disable interrupts, so a
  // long line can overflow the Uno's 64-byte UART TX buffer.
  Serial.print(tag);
  Serial.print(addr);
  Serial.print('R');
  Serial.print(reg);
  Serial.print(' ');
  Serial.print(len);
  Serial.print(':');
  for (uint8_t i = 0; i < len; ++i) {
    Serial.print(' ');
    if (buf[i] < 16) Serial.print('0');
    Serial.print(buf[i], HEX);
  }
  Serial.println();
}

// Diagnostic only: query every ADB address without altering device assignments.
// This is useful for older trackballs that do not use the conventional address 3.
static void scan_bus() {
  uint8_t buf[8];
  Serial.println(F("ADB scan begin"));
  for (uint8_t addr = 0; addr < 16; ++addr) {
    uint8_t len = adb_talk(addr, 0, buf, sizeof(buf));
    if (len) print_packet("A", addr, 0, buf, len);
    delay(2);
  }
  Serial.println(F("ADB scan end"));
}

void setup() {
  data_release();
  Serial.begin(115200);
  delay(200);
  Serial.println(F("ADB host probe: D2 DATA, external 4.7k pull-up"));
  Serial.println(F("PSW unused; trackball must be isolated"));
  adb_reset();
}

void loop() {
  static uint32_t last_status = 0;
  uint8_t buf[8];

  // The RPi bridge sends "L <hex>" to update keyboard LEDs. ADB register 2
  // expects two bytes; the low three bits are active-low LED state.
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'L') {
      while (Serial.available() && Serial.peek() == ' ') Serial.read();
      int value = Serial.parseInt();
      uint8_t led[2] = {0xFF, (uint8_t)~value};
      adb_listen(2, 2, led, 2);
    } else if (c == 'A') {
      scan_bus();
    }
  }

  // Address 3 is the conventional ADB mouse/trackball address; address 2 is
  // the conventional ADB keyboard address. Both devices share the bus.
  if (millis() - last_status >= 1000) {
    uint8_t len = adb_talk(3, 3, buf, sizeof(buf));
    if (len) print_packet("S", 3, 3, buf, len);
    else Serial.println(F("S3 no-response"));
    len = adb_talk(2, 3, buf, sizeof(buf));
    if (len) print_packet("K", 2, 3, buf, len);
    else Serial.println(F("K2 no-response"));
    last_status = millis();
  }

  uint8_t len = adb_talk(2, 0, buf, sizeof(buf));
  if (len) print_packet("K", 2, 0, buf, len);

  len = adb_talk(3, 0, buf, sizeof(buf));
  if (len) print_packet("D", 3, 0, buf, len);

  // Keep the ADB poll cadence responsive. The old 80 ms delay was plainly
  // visible as cursor/key lag and could miss short keyboard register-0 data.
  // Some older ADB keyboards lose events below roughly 8 ms. Ten ms remains
  // responsive while giving reliable make/break delivery.
  delay(10);
}

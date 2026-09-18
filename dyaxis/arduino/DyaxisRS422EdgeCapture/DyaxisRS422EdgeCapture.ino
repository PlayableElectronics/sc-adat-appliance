// Passive Dyaxis RS-422 edge recorder for a dedicated Arduino Nano.
// D2 is input-only; D0/D1 are reserved for USB serial and never connect to
// the Dyaxis signal. The Nano never drives the YL-128 or either differential
// pair.
#include <Arduino.h>

const uint8_t CAPTURE_PIN = 2;
const uint32_t USB_BAUD = 1000000UL;
const uint32_t TIMER_HZ = 2000000UL; // 16 MHz / Timer1 prescaler 8
const uint8_t RING_SIZE = 96;
const uint8_t MAGIC[8] = {'D','Y','A','X','E','D','G','1'};
const uint8_t VERSION = 1;
const uint8_t FRAME_HEADER = 0xA0, FRAME_START = 0xA1, FRAME_EDGE = 0xA2;
const uint8_t FRAME_OVERFLOW = 0xA3, FRAME_STOP = 0xA4, FRAME_READY = 0xA5;

struct Edge { uint32_t tick; uint8_t level; };
volatile Edge ring[RING_SIZE];
volatile uint8_t ringHead = 0, ringTail = 0;
volatile uint32_t timerHigh = 0, lostEvents = 0;
volatile bool capturing = false;
uint32_t lastSentTick = 0, lastReportedLoss = 0;

ISR(TIMER1_OVF_vect) { ++timerHigh; }

uint32_t nowTicks() {
  uint32_t high; uint16_t low; uint8_t status = SREG;
  cli(); high = timerHigh; low = TCNT1;
  if ((TIFR1 & _BV(TOV1)) && low < 0x8000) ++high;
  SREG = status;
  return (high << 16) | low;
}

void onEdge() {
  if (!capturing) return;
  uint8_t next = (uint8_t)((ringHead + 1) % RING_SIZE);
  if (next == ringTail) { ++lostEvents; return; }
  ring[ringHead].tick = nowTicks();
  ring[ringHead].level = (PIND & _BV(PD2)) ? 1 : 0;
  ringHead = next;
}

void putU16(uint16_t value) { Serial.write((uint8_t)value); Serial.write((uint8_t)(value >> 8)); }
void putU32(uint32_t value) {
  Serial.write((uint8_t)value); Serial.write((uint8_t)(value >> 8));
  Serial.write((uint8_t)(value >> 16)); Serial.write((uint8_t)(value >> 24));
}

void sendHeader(uint8_t initial) {
  Serial.write(MAGIC, sizeof(MAGIC)); Serial.write(VERSION); Serial.write(FRAME_HEADER);
  putU32(TIMER_HZ); Serial.write(initial); Serial.write((uint8_t)0); putU16(RING_SIZE);
}
void sendOverflow(uint32_t count) {
  Serial.write(FRAME_OVERFLOW); putU32(count); putU32(count - lastReportedLoss);
  lastReportedLoss = count;
}

void drainEdges() {
  while (true) {
    Edge edge; uint32_t loss;
    noInterrupts();
    if (ringTail == ringHead) { interrupts(); break; }
    edge = ring[ringTail]; ringTail = (uint8_t)((ringTail + 1) % RING_SIZE);
    loss = lostEvents; interrupts();
    if (loss != lastReportedLoss) sendOverflow(loss);
    Serial.write(FRAME_EDGE); putU32(edge.tick - lastSentTick); Serial.write(edge.level);
    lastSentTick = edge.tick;
  }
}

void startCapture() {
  noInterrupts(); ringHead = ringTail = 0; lostEvents = 0; timerHigh = 0; TCNT1 = 0;
  TIFR1 = _BV(TOV1); uint8_t initial = (PIND & _BV(PD2)) ? 1 : 0;
  lastSentTick = lastReportedLoss = 0; capturing = true; interrupts();
  sendHeader(initial); Serial.write(FRAME_START); putU32(0); Serial.write(initial);
}

void stopCapture() {
  noInterrupts(); capturing = false; interrupts(); drainEdges();
  noInterrupts(); uint32_t stop = nowTicks(), loss = lostEvents; interrupts();
  if (loss != lastReportedLoss) sendOverflow(loss);
  Serial.write(FRAME_STOP); putU32(stop); putU32(loss); Serial.flush();
}

void setupTimer() { TCCR1A = 0; TCCR1B = _BV(CS11); TIMSK1 = _BV(TOIE1); }
void setup() {
  pinMode(CAPTURE_PIN, INPUT); Serial.begin(USB_BAUD); setupTimer();
  attachInterrupt(digitalPinToInterrupt(CAPTURE_PIN), onEdge, CHANGE);
  Serial.write(FRAME_READY); Serial.flush();
}
void loop() {
  drainEdges();
  if (Serial.available()) { int command = Serial.read(); if (command == 'R') startCapture(); if (command == 'S') stopCapture(); }
  if (capturing) { noInterrupts(); uint32_t loss = lostEvents; interrupts(); if (loss != lastReportedLoss) sendOverflow(loss); }
}

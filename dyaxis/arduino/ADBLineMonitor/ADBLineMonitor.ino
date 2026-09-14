// Passive ADB wiring check for Arduino Uno.
// D2 is input-only here: this sketch never drives the ADB DATA line.
const uint8_t ADB_DATA_PIN = 2;
volatile uint32_t edgeCount = 0;
volatile uint8_t lastEdgeLevel = 1;

void onDataChange() {
  lastEdgeLevel = digitalRead(ADB_DATA_PIN);
  ++edgeCount;
}

void setup() {
  pinMode(ADB_DATA_PIN, INPUT); // external ADB pull-up should provide HIGH
  Serial.begin(115200);
  delay(200);
  attachInterrupt(digitalPinToInterrupt(ADB_DATA_PIN), onDataChange, CHANGE);
  Serial.println(F("ADB passive line monitor"));
  Serial.println(F("DATA is input-only; no ADB commands are transmitted."));
}

void loop() {
  static uint32_t lastReport = 0;
  if (millis() - lastReport >= 1000) {
    noInterrupts();
    uint32_t edges = edgeCount;
    uint8_t level = lastEdgeLevel;
    interrupts();
    Serial.print(F("DATA="));
    Serial.print(digitalRead(ADB_DATA_PIN) ? F("HIGH") : F("LOW"));
    Serial.print(F(" edges/s="));
    Serial.println(edges);
    edgeCount = 0;
    lastReport = millis();
  }
}

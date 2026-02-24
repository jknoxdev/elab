/*
  PROJECT: null-key v5 - RGB EDITION (Active Low / Common Anode)
  HARDWARE: SparkFun Pro Micro (ATmega32U4) 3.3V/8MHz
*/

#include <HID-Project.h>

// --- PIN DEFINITIONS ---
const int BTN_MUTE = 2;
const int BTN_BOSS = 5;
const int BTN_LOCK = 8;

const int LED_RED   = 10;
const int LED_GREEN = 6;
const int LED_BLUE  = 9;

// --- STATE VARIABLES ---
int lastStateMute = HIGH;
int lastStateBoss = HIGH;
int lastStateLock = HIGH;

bool isMuted = false;
bool isBossMode = false;
bool isLocked = false;

// --- HELPER: Set Color (Active Low Logic) ---
// 0 = Pin HIGH (Off), 255 = Pin LOW (Full Brightness)
void setRGB(int r, int g, int b) {
  analogWrite(LED_RED,   255 - r); 
  analogWrite(LED_GREEN, 255 - g);
  analogWrite(LED_BLUE,  255 - b);
}

void setup() {
  // Set pins to HIGH (Off for Active Low) BEFORE pinMode to prevent a bright flash
  digitalWrite(LED_RED, HIGH);
  digitalWrite(LED_GREEN, HIGH);
  digitalWrite(LED_BLUE, HIGH);
  
  pinMode(LED_RED, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_BLUE, OUTPUT);

  // Safety/Boot Delay - Yellow
  setRGB(255, 255, 0); 
  delay(4000);

  Serial.begin(9600);
  Consumer.begin();
  BootKeyboard.begin();

  pinMode(BTN_MUTE, INPUT_PULLUP);
  pinMode(BTN_BOSS, INPUT_PULLUP);
  pinMode(BTN_LOCK, INPUT_PULLUP);

  updateStatus(); 
}

void updateStatus() {
  // Priority order for LED feedback
  if (isLocked) {
    setRGB(255, 0, 0);   // RED
  } else if (isBossMode) {
    setRGB(100, 0, 255); // PURPLE
  } else if (isMuted) {
    setRGB(255, 50, 0);  // ORANGE-RED
  } else {
    setRGB(0, 255, 0);   // GREEN (Normal)
  }
}

void loop() {
  // --- MUTE ---
  int readMute = digitalRead(BTN_MUTE);
  if (readMute != lastStateMute && readMute == LOW) {
      Consumer.write(MEDIA_VOLUME_MUTE);
      isMuted = !isMuted;
      updateStatus();
      delay(200); // Debounce
  }
  lastStateMute = readMute;

  // --- BOSS KEY (Win+D) ---
  int readBoss = digitalRead(BTN_BOSS);
  if (readBoss != lastStateBoss && readBoss == LOW) {
      BootKeyboard.press(KEY_LEFT_GUI);
      BootKeyboard.write('d');
      BootKeyboard.releaseAll();
      isBossMode = !isBossMode;
      updateStatus();
      delay(300);
  }
  lastStateBoss = readBoss;

  // --- LOCK (Win+L) ---
  int readLock = digitalRead(BTN_LOCK);
  if (readLock != lastStateLock && readLock == LOW) {
      BootKeyboard.press(KEY_LEFT_GUI);
      BootKeyboard.write('l');
      BootKeyboard.releaseAll();
      isLocked = !isLocked;
      updateStatus();
      delay(500);
  }
  lastStateLock = readLock;
}

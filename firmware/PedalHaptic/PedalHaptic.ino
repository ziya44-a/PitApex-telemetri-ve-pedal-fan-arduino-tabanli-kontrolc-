// PitApex / Pedal Haptic v4 - Arduino Uno + L293D Motor Shield (Adafruit Motor Shield V1 / AFMotor)
// 4 MOTOR CIKISI: M1, M2, M3, M4. Her cikis PC'den secilen bir ise baglanir: pedal titresim motoru VEYA fan.
//
// Komutlar (satir sonu '\n' ile):
//   M<1-4>,<guc 0-255>,<frekans x10 Hz>,<darbe orani %>   ornek: M3,200,120,50  (M3, 12.0 Hz, %50)
//        frekans 0 = surekli titresim. Her motorun KENDI 150 ms zaman asimi vardir (komut gelmezse o motor durur).
//   F<1-4>,<0-255>   FAN hizi, secilen cikista            ornek: F4,128  (M4'teki fan %50)
//        Fan icin ayri zaman asimi vardir (FAN_TIMEOUT_MS). PC surekli F komutu gonderir; USB kopar / program
//        kapanirsa fan FAN_TIMEOUT_MS sonra durur.
//   F,<0-255>        ESKI bicim (v3 uyumu): LEGACY_FAN_MOTOR cikisindaki fan.
//   Q<0-3>           M1+M2 PWM frekansi: 0=1kHz 1=2kHz 2=8kHz 3=64kHz
//   P  -> "P" cevabi (gecikme olcumu)     V -> "V4" cevabi (kod surumu)
//
// Bir cikista hem titresim hem fan komutu varsa hizlisi uygulanir (max). PC arayuzu ayni cikisi iki isle
// birden kullanmanizi UYARIR; bir cikis fiziksel olarak tek cihaza baglanmalidir.
// M3 ve M4 PWM frekansi SABITTIR (~1 kHz, MOTOR34_1KHZ). 8/64 kHz secenekleri Timer0 hizini degistirip
// millis()/micros() zamanlamasini bozacagi icin BILEREK kullanilmaz. Q komutu yalniz M1/M2'yi etkiler.

#include <AFMotor.h>

#define FW_VERSION 4
#define NMOTORS 4

#define LEGACY_FAN_MOTOR 3        // yalniz eski "F,<hiz>" komutu icin (1-4)
#define MOTOR_TIMEOUT_MS 150
#define FAN_TIMEOUT_MS 2000

const uint8_t PWM_CODES[4] = { MOTOR12_1KHZ, MOTOR12_2KHZ, MOTOR12_8KHZ, MOTOR12_64KHZ };

AF_DCMotor motors[NMOTORS] = {
  AF_DCMotor(1, MOTOR12_1KHZ), AF_DCMotor(2, MOTOR12_1KHZ),
  AF_DCMotor(3, MOTOR34_1KHZ), AF_DCMotor(4, MOTOR34_1KHZ)
};

uint8_t       intensity[NMOTORS]  = {0, 0, 0, 0};
uint16_t      freq10[NMOTORS]     = {0, 0, 0, 0};
uint8_t       duty[NMOTORS]       = {50, 50, 50, 50};
int16_t       lastSpeed[NMOTORS]  = {-1, -1, -1, -1};
bool          outputOn[NMOTORS]   = {false, false, false, false};
bool          wasActive[NMOTORS]  = {false, false, false, false};
uint32_t      phaseStart[NMOTORS] = {0, 0, 0, 0};
unsigned long lastCmd[NMOTORS]    = {0, 0, 0, 0};

uint8_t       fanSpeed[NMOTORS]   = {0, 0, 0, 0};
unsigned long lastFanCmd[NMOTORS] = {0, 0, 0, 0};

char buf[32];
uint8_t len = 0;

void applyMotor(uint8_t m) {
  int16_t sp = outputOn[m] ? intensity[m] : 0;
  if (fanSpeed[m] > sp) sp = fanSpeed[m];
  if (sp != lastSpeed[m]) {
    lastSpeed[m] = sp;
    motors[m].setSpeed(sp);
  }
}

void setPwmCode(uint8_t c) {
  motors[0] = AF_DCMotor(1, PWM_CODES[c]);
  motors[1] = AF_DCMotor(2, PWM_CODES[c]);
  for (uint8_t i = 0; i < 2; i++) {
    motors[i].setSpeed(0);
    motors[i].run(FORWARD);
    lastSpeed[i] = -1;
  }
}

void parseLine() {
  buf[len] = 0;
  if (buf[0] == 'P') { Serial.println('P'); return; }
  if (buf[0] == 'V') { Serial.print('V'); Serial.println(FW_VERSION); return; }
  if (buf[0] == 'Q') {
    int c = atoi(buf + 1);
    if (c >= 0 && c < 4) setPwmCode(c);
    return;
  }
  if (buf[0] == 'F') {                       // fan: "F<1-4>,<hiz>" veya eski "F,<hiz>"
    int idx = LEGACY_FAN_MOTOR - 1;                       // "F,<hiz>" (eski bicim)
    if (buf[1] >= '1' && buf[1] <= '4') idx = buf[1] - '1';
    else if (buf[1] != ',' && buf[1] != 0) return;        // "F9,10" gibi gecersiz cikis: yok say
    char* q = strchr(buf, ',');
    int v = atoi(q ? q + 1 : buf + 1);
    fanSpeed[idx] = constrain(v, 0, 255);
    lastFanCmd[idx] = millis();
    return;
  }
  if (buf[0] != 'M') return;
  int m = buf[1] - '1';
  if (m < 0 || m >= NMOTORS) return;
  char* p = strchr(buf, ',');
  if (!p) return;
  int s = atoi(p + 1);
  p = strchr(p + 1, ',');
  if (!p) return;
  int f = atoi(p + 1);
  int d = 50;
  p = strchr(p + 1, ',');
  if (p) d = atoi(p + 1);
  intensity[m] = constrain(s, 0, 255);
  freq10[m]    = constrain(f, 0, 1000);
  duty[m]      = constrain(d, 5, 95);
  lastCmd[m]   = millis();
}

void setup() {
  Serial.begin(115200);
  for (uint8_t i = 0; i < NMOTORS; i++) {
    motors[i].setSpeed(0);
    motors[i].run(FORWARD);
    lastCmd[i] = millis();
    lastFanCmd[i] = millis();
  }
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') { parseLine(); len = 0; }
    else if (c != '\r' && len < sizeof(buf) - 1) buf[len++] = c;
  }

  unsigned long nowMs = millis();
  uint32_t nowUs = micros();
  for (uint8_t i = 0; i < NMOTORS; i++) {
    if (nowMs - lastCmd[i] > MOTOR_TIMEOUT_MS) intensity[i] = 0;       // titresim motoru guvenlik zaman asimi
    if (nowMs - lastFanCmd[i] > FAN_TIMEOUT_MS) fanSpeed[i] = 0;       // fan icin ayri guvenlik zaman asimi
    if (intensity[i] == 0) {
      outputOn[i] = false;
      wasActive[i] = false;
    } else {
      if (!wasActive[i]) { wasActive[i] = true; phaseStart[i] = nowUs; }  // darbe hep ACIK baslar
      if (freq10[i] == 0) {
        outputOn[i] = true;
      } else {
        uint32_t period = 10000000UL / freq10[i];          // mikrosaniye
        uint32_t onTime = period * duty[i] / 100;
        uint32_t el = nowUs - phaseStart[i];
        if (el >= period) { phaseStart[i] = nowUs; el = 0; }
        outputOn[i] = el < onTime;
      }
    }
    applyMotor(i);
  }
}

// PitApex / LED Matrix v1 - MAX7219 8x8 LED matris modulu (AYRI bir Arduino; pedal/fan Arduino'suyla ayni DEGIL)
// Kutuphane: "LedControl" (Eberhard Fahle) - Arduino IDE > Kutuphane Yoneticisi'nden kur.
//
// Baglanti (varsayilan, asagidaki PIN_* satirlariyla degistirilebilir):
//   MAX7219 VCC -> 5V    GND -> GND    DIN -> D12    CLK -> D11    CS (LOAD) -> D10
//
// Komutlar (115200 baud, satir sonu '\n'):
//   D,<16 hex>        goruntu: 8 satir, her satir 2 hex karakter (ilk satir ust, bit7 = sol sutun)   ornek: D,3C66666666663C00
//   D<n>,<16 hex>     zincirli n. modul (0 tabanli); n yazilmazsa 0. modul
//   B,<0-15>          parlaklik
//   C                 hepsini temizle
//   V -> "LED1"       kod surumu (PC arayuzu bununla LED kartini taniyor)
//   P -> "P"          gecikme olcumu
// PC her ~1 sn goruntuyu tekrar gonderir. TIMEOUT_MS boyunca komut gelmezse (USB koptu / program kapandi) ekran temizlenir.
// Modullerin kablolamasi farkli olabildigi icin yon (donme/ayna) PC arayuzunden ayarlanir; burada degistirmen gerekmez.

#include <LedControl.h>

#define LED_FW_VERSION 1
#define PIN_DIN 12
#define PIN_CLK 11
#define PIN_CS 10
#define NUM_DEVICES 1
#define TIMEOUT_MS 3000

LedControl lc = LedControl(PIN_DIN, PIN_CLK, PIN_CS, NUM_DEVICES);

char buf[40];
uint8_t len = 0;
unsigned long lastCmd = 0;
bool blank = true;

int hexval(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  return -1;
}

void clearAll() {
  for (uint8_t d = 0; d < NUM_DEVICES; d++) lc.clearDisplay(d);
  blank = true;
}

void parseLine() {
  buf[len] = 0;
  if (buf[0] == 'P') { Serial.println('P'); return; }
  if (buf[0] == 'V') { Serial.print("LED"); Serial.println(LED_FW_VERSION); return; }
  if (buf[0] == 'C') { clearAll(); lastCmd = millis(); return; }
  if (buf[0] == 'B') {
    char* q = strchr(buf, ',');
    int v = constrain(atoi(q ? q + 1 : buf + 1), 0, 15);
    for (uint8_t d = 0; d < NUM_DEVICES; d++) lc.setIntensity(d, v);
    lastCmd = millis();
    return;
  }
  if (buf[0] == 'D') {
    int dev = 0;
    if (buf[1] >= '0' && buf[1] <= '9') dev = buf[1] - '0';
    else if (buf[1] != ',') return;
    if (dev < 0 || dev >= NUM_DEVICES) return;
    char* p = strchr(buf, ',');
    if (!p || strlen(p + 1) != 16) return;                 // tam 16 hex karakter olmali, yoksa yok say
    uint8_t rows[8];
    for (uint8_t r = 0; r < 8; r++) {
      int hi = hexval(p[1 + 2 * r]), lo = hexval(p[2 + 2 * r]);
      if (hi < 0 || lo < 0) return;
      rows[r] = (hi << 4) | lo;
    }
    for (uint8_t r = 0; r < 8; r++) lc.setRow(dev, r, rows[r]);
    blank = false;
    lastCmd = millis();
  }
}

void setup() {
  Serial.begin(115200);
  for (uint8_t d = 0; d < NUM_DEVICES; d++) {
    lc.shutdown(d, false);          // uyku modundan cik
    lc.setIntensity(d, 4);
    lc.clearDisplay(d);
  }
  lastCmd = millis();
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') { parseLine(); len = 0; }
    else if (c != '\r' && len < sizeof(buf) - 1) buf[len++] = c;
  }
  if (!blank && millis() - lastCmd > TIMEOUT_MS) clearAll();   // guvenlik: eski vites ekranda kalmasin
}

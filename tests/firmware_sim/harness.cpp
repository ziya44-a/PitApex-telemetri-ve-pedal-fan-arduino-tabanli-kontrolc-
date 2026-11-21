// Komut satirindan okunan betikle PedalHaptic.ino'yu calistirir.
//  feed <metin>  : seri porta metin + '\n' yazar      time <ms> : saati ayarla
//  loop [n]      : loop() cagirir (n kez)              speeds    : 4 cikisin son PWM degerleri
//  out           : Arduino'nun seriye yazdiklarini yazdir ve temizle
#include "Arduino.h"
unsigned long g_ms = 0;
SerialShim Serial;
int g_speed[4] = {-1, -1, -1, -1};
#include "../../firmware/PedalHaptic/PedalHaptic.ino"

#include <iostream>
#include <sstream>
int main() {
  setup();
  std::string line;
  while (std::getline(std::cin, line)) {
    std::istringstream is(line);
    std::string cmd;
    is >> cmd;
    if (cmd == "feed") {
      std::string rest;
      std::getline(is, rest);
      if (!rest.empty() && rest[0] == ' ') rest.erase(0, 1);
      for (char c : rest) Serial.in.push_back(c);
      Serial.in.push_back('\n');
    } else if (cmd == "time") {
      unsigned long t; is >> t; g_ms = t;
    } else if (cmd == "loop") {
      int n = 1; is >> n; if (n < 1) n = 1;
      for (int i = 0; i < n; i++) loop();
    } else if (cmd == "speeds") {
      printf("%d %d %d %d\n", g_speed[0], g_speed[1], g_speed[2], g_speed[3]);
    } else if (cmd == "out") {
      printf("OUT:%s\n", Serial.out.c_str());
      Serial.out.clear();
    }
  }
  return 0;
}

// LedMatrix.ino'yu ana makinede calistirir. Komutlar: feed <metin> | time <ms> | loop | rows | bright | out
#include "Arduino.h"
unsigned long g_ms = 0;
SerialShim Serial;
uint8_t g_rows[4][8];
int g_intensity[4] = {-1, -1, -1, -1};
bool g_shutdown[4] = {true, true, true, true};
#include "../../firmware/LedMatrix/LedMatrix.ino"
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
      std::string rest; std::getline(is, rest);
      if (!rest.empty() && rest[0] == ' ') rest.erase(0, 1);
      for (char c : rest) Serial.in.push_back(c);
      Serial.in.push_back('\n');
    } else if (cmd == "time") { unsigned long t; is >> t; g_ms = t; }
    else if (cmd == "loop") { loop(); }
    else if (cmd == "rows") { for (int r = 0; r < 8; r++) printf("%02X", g_rows[0][r]); printf("\n"); }
    else if (cmd == "rows1") { for (int r = 0; r < 8; r++) printf("%02X", g_rows[1][r]); printf("\n"); }
    else if (cmd == "bright") printf("%d %d\n", g_intensity[0], g_shutdown[0] ? 1 : 0);
    else if (cmd == "out") { printf("OUT:%s\n", Serial.out.c_str()); Serial.out.clear(); }
  }
  return 0;
}

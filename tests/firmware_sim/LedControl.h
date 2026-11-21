#pragma once
#include "Arduino.h"
extern uint8_t g_rows[4][8];
extern int g_intensity[4];
extern bool g_shutdown[4];
class LedControl {
 public:
  LedControl(int, int, int, int) {}
  void shutdown(int a, bool s) { g_shutdown[a] = s; }
  void setIntensity(int a, int v) { g_intensity[a] = v; }
  void clearDisplay(int a) { for (int r = 0; r < 8; r++) g_rows[a][r] = 0; }
  void setRow(int a, int r, uint8_t v) { g_rows[a][r] = v; }
};

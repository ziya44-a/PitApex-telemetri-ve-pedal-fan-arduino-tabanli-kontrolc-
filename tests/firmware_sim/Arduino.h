// Ana makinede PedalHaptic.ino'yu denemek icin Arduino calisma ortami taklidi (sadece test).
#pragma once
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <string>
#include <deque>

#define constrain(x, a, b) ((x) < (a) ? (a) : ((x) > (b) ? (b) : (x)))

extern unsigned long g_ms;
inline unsigned long millis() { return g_ms; }
inline unsigned long micros() { return g_ms * 1000UL; }

struct SerialShim {
  std::deque<char> in;
  std::string out;
  void begin(long) {}
  int available() { return (int)in.size(); }
  char read() { char c = in.front(); in.pop_front(); return c; }
  void println(char c) { out += c; out += '\n'; }
  void println(const char* s) { out += s; out += '\n'; }
  void print(char c) { out += c; }
  void print(const char* s) { out += s; }
  void print(int v) { out += std::to_string(v); }
  void println(int v) { out += std::to_string(v); out += '\n'; }
};
extern SerialShim Serial;

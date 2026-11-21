#pragma once
#include "Arduino.h"
#define MOTOR12_64KHZ 0
#define MOTOR12_8KHZ 1
#define MOTOR12_2KHZ 2
#define MOTOR12_1KHZ 3
#define MOTOR34_64KHZ 4
#define MOTOR34_8KHZ 5
#define MOTOR34_1KHZ 6
#define FORWARD 1
extern int g_speed[4];
class AF_DCMotor {
 public:
  int n;
  AF_DCMotor(int num = 1, int freq = 0) : n(num) { (void)freq; }
  void setSpeed(int s) { g_speed[n - 1] = s; }
  void run(int) {}
};

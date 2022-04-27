// LowVoltageShutdown_Triton.ino
//
// Last Updated: 04/18/22 | Primary Contact: Michael Fuhrer, mfuhrer@vt.edu
//
// Based off of LowVoltageShutdown example from SleepyPi2 arduino library.
// Constantly measures battery voltage and may advertise readings to Raspberry Pi over I2C. Shuts down RPi if
// voltage drops below specified thresholds.

// **** INCLUDES *****
#include "SleepyPi2.h"
#include <TimeLib.h>
#include <LowPower.h>
#include <PCF8523.h>
#include <Wire.h>

#define SLAVE_ADDR 0x70

#define POWER_ON_VOLTAGE    24.2
#define POWER_OFF_VOLTAGE   24.12
#define FORCE_OFF_VOLTAGE   23.5

#define LOW_VOLTAGE_TIME_MS 10000ul    // 10 seconds

typedef union{
  float val;
  unsigned char bytes[4];
}FLOATUNION_t;

const int LED_PIN = 13;

volatile bool  alarmFired = false;
bool state = LOW;
unsigned long  time,
               timeLow = 0,
               timeVeryLow = 0;
FLOATUNION_t supply_voltage;  

void alarm_isr()
{
    alarmFired = true;
}

void setup()
{
    supply_voltage.val = 0;
    // Initialize serial communication:
    Serial.begin(9600);
    Serial.println("Start...");
    
    // Configure "Standard" LED pin
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN,LOW);		// Switch off LED
  
    SleepyPi.enablePiPower(false);
    SleepyPi.enableExtPower(false);

    // Allow wake up alarm to trigger interrupt on falling edge.
    attachInterrupt(0, alarm_isr, FALLING);    // Alarm pin
     
    // Initialize I2C communication:
    Serial.println("Beginning I2C wire...");
    Wire.begin(SLAVE_ADDR);
    Wire.onRequest(voltageRequest);
}

void loop()
{
    bool   pi_running;

    // Enter power down state with ADC and BOD module disabled.
    // Wake up when wake up pin is low.
    pi_running = SleepyPi.checkPiStatus(true);  // Cut Power if we detect Pi not running
    if(pi_running == false){
        delay(500);
        Serial.println("Pi not running...");
        pi_running = SleepyPi.checkPiStatus(false);
    }

    time = millis();
    // Check for rollover
    if(time < timeLow ||
       time < timeVeryLow){
        timeLow = time;
        timeVeryLow = time;
    }

    if(alarmFired == true){
        SleepyPi.ackTimer1();
        alarmFired = false;
    }
    Serial.println("here");
    // Boot or shutdown based on supply voltage
    delay(10);  // voltage reading is artificially high if we don't delay first
    supply_voltage.val = SleepyPi.supplyVoltage();
    Serial.println(supply_voltage.val);
    if(pi_running == true){
        if(supply_voltage.val > POWER_OFF_VOLTAGE){
            // Voltage is normal; reset the low voltage counter
            timeLow = time;
        }
        if(supply_voltage.val > FORCE_OFF_VOLTAGE){
            timeVeryLow = time;
        }
        // Check for low voltage
        // Allow override with the button during low voltage state,
        // but not during very low voltage / force off state.
        if(time - timeVeryLow > LOW_VOLTAGE_TIME_MS ||
           time - timeLow > LOW_VOLTAGE_TIME_MS){
            // Start a shutdown
            Serial.println("Shutting down");
            SleepyPi.piShutdown();
            SleepyPi.enableExtPower(false);
        }
        delay(500);
    } else {
        // Check for voltage recovery
        if(supply_voltage.val >= POWER_ON_VOLTAGE){
            // Switch on the Pi
            SleepyPi.enablePiPower(true);
            SleepyPi.enableExtPower(true);
        }
    }
}

void voltageRequest(){
  Wire.write(supply_voltage.bytes, 4);
}

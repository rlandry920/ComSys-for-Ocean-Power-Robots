// 
// This example implements a low voltage disconnect function like a UPS. When
// supply voltage falls below the low threshold for 30 seconds, the Arduino
// signals the RPi to shutdown. When the voltage recovers to above the high
// threshold, the RPi boots.
//
// The low voltage shutdown can be overridden by pressing the button. The RPi
// will wake on button press and stay powered for one hour. Extend the time to
// one hour again by pressing the button. The override is ignored when voltage
// is below the force off voltage.
//
// To shutdown the RPi, hold the button for 2-8 seconds. If the button is held
// down more than 8 seconds the Sleepy Pi will cut the power to the RPi
// regardless of any handshaking.
// 
// While powered, the supply voltage prints to the serial monitor twice
// per second.
//

// **** INCLUDES *****
#include "SleepyPi2.h"
#include <TimeLib.h>
#include <LowPower.h>
#include <PCF8523.h>
#include <Wire.h>

#define SLAVE_ADDR 0x70

#define POWER_ON_VOLTAGE    12
#define POWER_OFF_VOLTAGE   10
#define FORCE_OFF_VOLTAGE   8

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

// Set the period to check voltage recovery. Higher values improve power savings.
eTIMER_TIMEBASE  PeriodicTimer_Timebase     = eTB_SECOND;   // e.g. Timebase set to seconds. Other options: eTB_MINUTE, eTB_HOUR
uint8_t          PeriodicTimer_Value        = 10;           // Timer Interval in units of Timebase e.g 10 seconds

void alarm_isr()
{
    alarmFired = true;
}

void button_isr()
{
  // Use in case of RTC initialization failure.
  SleepyPi.enablePiPower(true);
  SleepyPi.enableExtPower(true);
  digitalWrite(LED_PIN, HIGH);
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
    attachInterrupt(1, button_isr, LOW);
  
    // FIXME: Not sure why we need this line
    SleepyPi.rtcClearInterrupts();
    
    Serial.println("RTC and Alarms Configured.");

    // Initialize I2C communication:
    Serial.println("Beginning I2C wire...");
    Wire.begin(SLAVE_ADDR);
    Wire.onRequest(voltageRequest);
    
    SleepyPi.rtcInit(true);
    
    // Set the Periodic Timer
    SleepyPi.setTimer1(PeriodicTimer_Timebase, PeriodicTimer_Value);
}

void loop()
{
    bool   pi_running;

    // Enter power down state with ADC and BOD module disabled.
    // Wake up when wake up pin is low.
    pi_running = SleepyPi.checkPiStatus(true);  // Cut Power if we detect Pi not running
    if(pi_running == false){
        delay(500);
        Serial.println("TritonRobot is not running..");
        SleepyPi.powerDown(SLEEP_FOREVER, ADC_OFF, BOD_OFF); 
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

    // Boot or shutdown based on supply voltage
    delay(10);  // voltage reading is artificially high if we don't delay first
    supply_voltage.val = SleepyPi.supplyVoltage();
    String my_voltage = "Voltage: ";
    my_voltage.concat(supply_voltage.val);
    Serial.println(my_voltage);
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
        if(time - timeVeryLow > LOW_VOLTAGE_TIME_MS || (
           time - timeLow > LOW_VOLTAGE_TIME_MS)){
            // Start a shutdown
            Serial.println("Shutting down..");
            SleepyPi.piShutdown();
            SleepyPi.enableExtPower(false);
        }
        delay(500);
    } else {
        // Check for voltage recovery
        if(supply_voltage.val >= POWER_ON_VOLTAGE){
            // Switch on the Pi
            Serial.println("Switching on..");
            SleepyPi.enablePiPower(true);
            SleepyPi.enableExtPower(true);
        }
    }
}

void voltageRequest(){
  Serial.println("Received I2C request!");
  Wire.write(supply_voltage.bytes, 4);
}

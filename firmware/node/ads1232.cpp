// firmware/node/ads1232.cpp
// ADS1232 HAL — bit-bang implementation.
// Protocol: DRDY/DOUT goes LOW when conversion ready.
// Clock 24 bits out MSB first. Data valid during SCLK HIGH phase.
// delayMicroseconds(1) required on every GPIO edge — ESP32-C3 at 160MHz is
// faster than ADS1232 minimum setup times without this delay.
#include "ads1232.h"
#include "config.h"

void ads1232_init(void) {
    pinMode(ADS_PIN_SCLK, OUTPUT);
    pinMode(ADS_PIN_DOUT, INPUT);      // DOUT is also DRDY — no pull-up needed,
    pinMode(ADS_PIN_PDWN, OUTPUT);     // ADS1232 drives it actively
    pinMode(ADS_PIN_A0,   OUTPUT);

    digitalWrite(ADS_PIN_SCLK, LOW);   // clock idle low
    digitalWrite(ADS_PIN_A0,   ADS_CHANNEL);  // select channel 1

    ads1232_power_up();
}

void ads1232_power_up(void) {
    digitalWrite(ADS_PIN_PDWN, HIGH);
    delay(ADS_WARMUP_MS);              // oscillator needs time to stabilise
}

void ads1232_power_down(void) {
    digitalWrite(ADS_PIN_PDWN, LOW);
}

bool ads1232_is_ready(void) {
    return digitalRead(ADS_PIN_DOUT) == LOW;
}

int32_t ads1232_read_raw(void) {
    // Wait for DRDY to go LOW (conversion complete)
    uint32_t deadline = millis() + ADS_READY_TIMEOUT_MS;
    while (!ads1232_is_ready()) {
        if (millis() > deadline) {
            return ADS1232_READ_ERROR;  // hardware not responding
        }
    }

    int32_t data = 0;

    // Disable interrupts for the entire 24-bit read.
    // A missed or extra edge corrupts the entire reading.
    noInterrupts();

    for (int i = 23; i >= 0; i--) {
        // Rising edge: ADS1232 presents the next bit on DOUT
        digitalWrite(ADS_PIN_SCLK, HIGH);
        delayMicroseconds(1);           // MANDATORY — setup time

        // Sample DOUT while SCLK is HIGH
        if (digitalRead(ADS_PIN_DOUT)) {
            data |= (1 << i);
        }

        // Falling edge: ADS1232 advances to next bit
        digitalWrite(ADS_PIN_SCLK, LOW);
        delayMicroseconds(1);           // MANDATORY — hold time
    }

    interrupts();

    // ADS1232 output is 24-bit two's complement.
    // Sign-extend bit 23 to fill the 32-bit int.
    if (data & 0x800000) {
        data |= 0xFF000000;
    }

    return data;
}

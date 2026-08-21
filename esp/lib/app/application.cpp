#include "Application.h"
#include "I2CMasterControl.h"
<<<<<<< HEAD
#include "pinMapping.h"

#include "OtaManager.h"
#include "DebugLogger.h"
=======
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61

Application::Application()
    : _uart(Serial),
      _storage(),
      _display(),
      _pi(_uart, _storage, _display),
      _gpioExpander(0x20),
      _inputs(_gpioExpander),
<<<<<<< HEAD
      _wakeupReason(WakeupReason::Reason::UNKNOWN),
      _wifi()
{
}

#define Serial DebugSerial

void Application::begin()
{
    Serial.begin(115200);
    delay(100);

    // Status-LED
    pinMode(Pins::ESP_DTR, OUTPUT);

    _wakeupReason = WakeupReason::getReason();

    Serial.print("[CHECK] Wakeup reason: ");
    Serial.println(WakeupReason::toString(_wakeupReason));

    _uart.begin(115200);

    I2CMasterControl::begin();

<<<<<<< HEAD
    I2CMasterControl::enable();
    I2CMasterControl::scan(Serial);
    I2CMasterControl::disable();

    I2CMasterControl::enable();

    bool framAvailable = _storage.begin();
    bool framWriteOk = false;
    bool framReadOk = false;

    if (framAvailable)
    {
        const String originalText = _storage.readText();
        const String testText = "FRAM read/write test";

        framWriteOk = _storage.writeText(testText);
        const String readText = _storage.readText();
        framReadOk = readText == testText;

        _storage.writeText(originalText);
    }

    Serial.println(framAvailable ? "[FRAM] Address OK" : "[FRAM] Address ERROR");
    Serial.println(framWriteOk ? "[FRAM] Write OK" : "[FRAM] Write ERROR");
    Serial.println(framReadOk ? "[FRAM] Read OK" : "[FRAM] Read ERROR");

    I2CMasterControl::disable();

    _display.begin();

    _gpioExpander.begin();

=======
    _display.begin();

    _gpioExpander.begin();
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61
    _inputs.begin();

    _pi.begin();

<<<<<<< HEAD
    if (_wifi.begin()) {
        DebugSerial.beginNetwork();
        OtaManager::begin("reflectionwall");
    }
    else {
        Serial.println("[CHECK] WiFi FAILED");
    }

    handleWakeup(_wakeupReason);

=======
    handleWakeup(_wakeupReason);
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61
}

void Application::handleWakeup(WakeupReason::Reason reason)
{
    switch (reason)
    {
<<<<<<< HEAD
        case WakeupReason::Reason::TIMER:
            _display.show("WakeupReason Reason-TIMER");
            break;

        case WakeupReason::Reason::INT_HLK:
            //_pi.requestText();
            _display.show("WakeupReason Reason-INT_HLK");
            break;

        case WakeupReason::Reason::INT_GPIO_EXP:
        {
            InputEvent event = _inputs.getEvent();

            Serial.print("[CHECK] Input event: ");
            Serial.println(static_cast<int>(event));

            switch (event)
=======
        case WakeupReason::Reason::TIMER: {
            _display.show("WakeupReason Reason-TIMER");
            break;
        }
        case WakeupReason::Reason::INT_HLK: {
            //_pi.requestText();
            _display.show("WakeupReason Reason-INT_HLK");
            break;
        }
        case WakeupReason::Reason::INT_GPIO_EXP:{
            InputEvent event = _inputs.getEvent();

            switch(event)
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61
            {
                case InputEvent::BT1:
                    _display.show("BTN1");
                    break;

                case InputEvent::BT2:
                    _display.show("BTN2");
                    break;

                case InputEvent::BT3:
                    _display.show("BTN3");
                    break;
<<<<<<< HEAD

                case InputEvent::BT4:
                {
                    bool state = _inputs.getButtonState(InputEvent::BT4);

                    Serial.print("[CHECK] BTN4 state: ");
                    Serial.println(state ? "HIGH" : "LOW");

                    if (state)
                        _display.show("BTN4 not pressed");
                    else
                        _display.show("BTN4");

                    break;
                }

                case InputEvent::BT5:
                {
                    bool state = _inputs.getButtonState(InputEvent::BT5);

                    Serial.print("[CHECK] BTN5 state: ");
                    Serial.println(state ? "HIGH" : "LOW");

                    if (state)
                        _display.show("BTN5 High");
                    else
                        _display.show("BTN5 Low");

                    break;
                }

                case InputEvent::BT6:
                {
                    bool state = _inputs.getButtonState(InputEvent::BT6);

                    Serial.print("[CHECK] BTN6 state: ");
                    Serial.println(state ? "HIGH" : "LOW");

                    if (state)
                        _display.show("BTN6 High");
                    else
                        _display.show("BTN6 Low");

                    break;
                }

                default:
                    break;
            }

            break;
        }

        case WakeupReason::Reason::SHUTDOWN_BUTTON:
            _display.show("WakeupReason Reason-SHUTDOWN_BUTTON");
            break;

        case WakeupReason::Reason::UNKNOWN:
            _display.show("WakeupReason Reason-UNKNOWN");
            break;

        default:
            _display.show("WakeupReason Reason-DEFAULT");
            break;
    }
    
    digitalWrite(Pins::ESP_DTR, LOW);
    //_display.show("Hello World");
    _display.show("888888888888888888888888");
}

unsigned long _ledTimer = 0;
bool _ledState = false;

void Application::loop()
{
    DebugSerial.handle();
    OtaManager::handle();
    
    // Non-blocking LED
    const unsigned long now = millis();

    if (now - _ledTimer >= 1000)
    {
        _ledTimer = now;

        _ledState = !_ledState;

        digitalWrite(
            Pins::ESP_DTR,
            _ledState ? HIGH : LOW
        );
    }

    //ESP.deepSleep(0);
    //_pi.loop();
}

// DIN3: RST
// DIN4: GPIO15
// DIN5: DTR
=======
                
                case InputEvent::BT4: {
                    bool state = _inputs.getButtonState(InputEvent::BT4);
                    if (state) {
                        _display.show("BTN4 not pressed");
                        // Noch undefiniert
                    } else {
                        _display.show("BTN4");
                        // Noch undefiniert
                    }
                    break;
                }
                
                case InputEvent::BT5: {
                    bool state = _inputs.getButtonState(InputEvent::BT5);
                    if (state) {
                        _display.show("BTN5 High");
                        // Speak Mode einschalten
                    } else {
                        _display.show("BTN5 Low");
                        // Speak Mode ausschalten
                    }
                    break;
                }

                case InputEvent::BT6: {
                    bool state = _inputs.getButtonState(InputEvent::BT6);
                    if (state) {
                        _display.show("BTN6 High");
                        // Raspberry Pi einschalten
                    } else {
                        _display.show("BTN6 Low");
                        // Raspberry Pi ausschalten
                    }
                    break;
                }
            }
            break;
        }

        case WakeupReason::Reason::SHUTDOWN_BUTTON: {
            _display.show("WakeupReason Reason-SHUTDOWN_BUTTON");
            break;
        }

        case WakeupReason::Reason::UNKNOWN: {
            _display.show("WakeupReason Reason-UNKNOWN");
        }

        default:
            break;
    }
}

void Application::loop()
{
    _pi.loop();
}
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61

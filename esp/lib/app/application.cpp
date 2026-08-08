#include "Application.h"
#include "I2CMasterControl.h"

Application::Application()
    : _uart(Serial),
      _storage(),
      _display(),
      _pi(_uart, _storage, _display),
      _gpioExpander(0x20),
      _inputs(_gpioExpander),
      _wakeupReason(WakeupReason::Reason::UNKNOWN)
{
}

void Application::begin()
{
    _wakeupReason = WakeupReason::getReason();

    Serial.begin(115200);
    Serial.println(WakeupReason::toString(_wakeupReason));

    _uart.begin(115200);

    I2CMasterControl::begin();

    _display.begin();

    _gpioExpander.begin();
    _inputs.begin();

    _pi.begin();

    handleWakeup(_wakeupReason);
}

void Application::handleWakeup(WakeupReason::Reason reason)
{
    switch (reason)
    {
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
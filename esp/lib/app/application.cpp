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
                case InputEvent::BUTTON_1:
                    _display.show("BTN1");
                    break;

                case InputEvent::BUTTON_2:
                    _display.show("BTN2");
                    break;

                case InputEvent::BUTTON_3:
                    _display.show("BTN3");
                    break;

                default:
                    break;
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
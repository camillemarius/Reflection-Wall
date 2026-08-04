#include "InputManager.h"


InputManager::InputManager(PCF8575& expander)
    : _expander(expander)
{
}


void InputManager::begin()
{
    _expander.read16();
}


InputEvent InputManager::getEvent()
{
    uint16_t state = _expander.read16();

    // LOW = Taster gedrückt
    if (!(state & (1 << 3)))
        return InputEvent::BUTTON_1;

    if (!(state & (1 << 4)))
        return InputEvent::BUTTON_2;

    if (!(state & (1 << 5)))
        return InputEvent::BUTTON_3;

    if (!(state & (1 << 10)))
        return InputEvent::BUTTON_4;

    if (!(state & (1 << 11)))
        return InputEvent::BUTTON_5;

    if (!(state & (1 << 12)))
        return InputEvent::BUTTON_6;

    return InputEvent::NONE;
}

void InputManager::setLed(InputEvent button, bool on)
{
    uint8_t pin = 0;

    switch (button)
    {
        case InputEvent::BUTTON_1: pin = 0;  break;
        case InputEvent::BUTTON_2: pin = 1;  break;
        case InputEvent::BUTTON_3: pin = 2;  break;
        case InputEvent::BUTTON_4: pin = 13; break;
        case InputEvent::BUTTON_5: pin = 14; break;
        case InputEvent::BUTTON_6: pin = 15; break;
        default: return;
    }

    // LED aktiv LOW
    _expander.setOutput(pin, !on);
}
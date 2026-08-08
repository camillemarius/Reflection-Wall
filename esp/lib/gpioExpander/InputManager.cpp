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
        return InputEvent::BT1;

    if (!(state & (1 << 4)))
        return InputEvent::BT2;

    if (!(state & (1 << 5)))
        return InputEvent::BT3;

    if (!(state & (1 << 10)))
        return InputEvent::BT4;

    if (!(state & (1 << 11)))
        return InputEvent::BT5;

    if (!(state & (1 << 12)))
        return InputEvent::BT6;

    return InputEvent::NONE;
}

bool InputManager::getButtonState(InputEvent button)
{
    uint8_t pin = 0;

    switch(button)
    {
        case InputEvent::BT1: pin = 3; break;
        case InputEvent::BT2: pin = 4; break;
        case InputEvent::BT3: pin = 5; break;
        case InputEvent::BT4: pin = 10; break;
        case InputEvent::BT5: pin = 11; break;
        case InputEvent::BT6: pin = 12; break;

        default:
            return true;
    }

    uint16_t state = _expander.read16();

    return (state & (1 << pin)) != 0;
}

void InputManager::setLed(InputEvent button, bool on)
{
    uint8_t pin = 0;

    switch (button)
    {
        case InputEvent::BT1: pin = 2;  break;
        case InputEvent::BT2: pin = 1;  break;
        case InputEvent::BT3: pin = 0;  break;
        case InputEvent::BT4: pin = 15; break;
        case InputEvent::BT5: pin = 14; break;
        case InputEvent::BT6: pin = 13; break;
        default: return;
    }

    // LED aktiv LOW
    _expander.setOutput(pin, !on);
}
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


    // PCF8575: LOW = aktiv
    /*if(!(state & (1 << 0)))
        return InputEvent::BUTTON_1;*/


    /*if(!(state & (1 << 1)))
        return InputEvent::BUTTON_2;*/


    /*if(!(state & (1 << 2)))
        return InputEvent::BUTTON_3;*/


    if(!(state & (1 << 8)))
        return InputEvent::BUTTON_4;


    if(!(state & (1 << 9)))
        return InputEvent::BUTTON_5;


    if(!(state & (1 << 10)))
        return InputEvent::BUTTON_6;


    return InputEvent::NONE;
}
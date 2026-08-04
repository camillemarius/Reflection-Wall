#pragma once

#include "PCF8575.h"
#include "InputEvent.h"

class InputManager
{
public:

    InputManager(PCF8575& expander);

    void begin();
    void setLed(InputEvent button, bool on);

    InputEvent getEvent();


private:

    PCF8575& _expander;
};
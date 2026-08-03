#pragma once

#include "UartHandler.h"
#include "TextStorage.h"
#include "Display.h"

class piCommunication
{
public:
    piCommunication(
        UartHandler& uart,
        TextStorage& storage,
        Display& display
    );

    void begin();
    void loop();
    void requestText();

private:
    UartHandler& _uart;
    TextStorage& _storage;
    Display& _display;
};
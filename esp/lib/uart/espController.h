#ifndef ESP_CONTROLLER_H
#define ESP_CONTROLLER_H

#include <Arduino.h>

#include "UartHandler.h"
#include "TextStorage.h"


class EspController
{

public:

    EspController(
        UartHandler &uart,
        TextStorage &storage
    );


    void begin();


    void loop();


    // Daten vom Raspberry Pi anfordern
    void requestText();


    // gespeicherten Text lesen
    String getText();


    bool hasText();



private:

    UartHandler &_uart;

    TextStorage &_storage;


    void handleMessage(
        String command,
        String data
    );


    void send(
        String command,
        String data
    );


};


#endif
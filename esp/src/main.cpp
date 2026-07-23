#include <Arduino.h>

#include "UartHandler.h"
#include "TextStorage.h"
#include "EspController.h"



UartHandler uart(
    Serial
);


TextStorage storage;


EspController esp(
    uart,
    storage
);



void setup()
{

    Serial.begin(
        115200
    );


    uart.begin(
        115200
    );


    esp.begin();


    delay(500);


    // Raspberry Pi nach Text fragen
    esp.requestText();

}



void loop()
{
    esp.loop();
}
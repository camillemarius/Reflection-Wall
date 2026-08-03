#ifndef UART_HANDLER_H
#define UART_HANDLER_H

#include <Arduino.h>


class UartHandler
{

public:

    UartHandler(
        HardwareSerial &serial
    );


    void begin(
        uint32_t baudrate
    );


    bool available();


    String readLine();


    void send(
        String message
    );


private:

    HardwareSerial &_serial;

};


#endif
#include "uartHandler.h"



UartHandler::UartHandler(
    HardwareSerial &serial
)
:
_serial(serial)
{

}



void UartHandler::begin(
    uint32_t baudrate
)
{

    _serial.begin(
        baudrate
    );

}



bool UartHandler::available()
{

    return _serial.available();

}



String UartHandler::readLine()
{

    return _serial.readStringUntil(
        '\n'
    );

}



void UartHandler::send(
    String message
)
{

    _serial.println(
        message
    );

}
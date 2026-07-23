#include "EspController.h"

#include "Protocol.h"
#include "Commands.h"



EspController::EspController(
    UartHandler &uart,
    TextStorage &storage
)
:
_uart(uart),
_storage(storage)
{

}

void EspController::begin() {
    _storage.begin();

}

void EspController::loop()
{

    if(!_uart.available()) {
        return;
    }

    String message =_uart.readLine();
    String command;
    String data;
    if(Protocol::decode(message,command,data)) {
        handleMessage(command, data);
    }
}

void EspController::requestText(){
    send(Commands::GET, Commands::TEXT);
}

void EspController::handleMessage(String command, String data) {
    /*
       Raspberry Pi Antwort:
       TEXT|Mein langer Text
    */
    if(command == Commands::TEXT) {
        if(_storage.save(data)) {
            send(Commands::SET,"TEXT_OK");
        }
        else {
            send(Commands::SET, "TEXT_ERROR");
        }
    }
    /* SET Anfrage */
    else if(command == Commands::SET) {
        send(Commands::SET, "OK");
    }
}

void EspController::send(String command, String data)
{
    String message = Protocol::encode(command, data);
    _uart.send(message);
}

String EspController::getText() {
    return _storage.load();
}

bool EspController::hasText() {
    return _storage.exists();
}
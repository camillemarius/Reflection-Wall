#include "piCommunication.h"

piCommunication::piCommunication(
    UartHandler& uart,
    TextStorage& storage,
    Display& display
)
    : _uart(uart),
      _storage(storage),
      _display(display)
{
}


void piCommunication::begin()
{
}


void piCommunication::loop()
{
}


void piCommunication::requestText()
{
}
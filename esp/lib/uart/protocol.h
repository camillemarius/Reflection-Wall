#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <Arduino.h>


class Protocol
{

public:

    static String encode(
        String command,
        String data
    );


    static bool decode(
        String message,
        String &command,
        String &data
    );


};


#endif
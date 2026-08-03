#include "protocol.h"


String Protocol::encode(
    String command,
    String data
)
{

    return command +
           "|" +
           data +
           "\n";

}



bool Protocol::decode(
    String message,
    String &command,
    String &data
)
{

    int pos = message.indexOf(
        '|'
    );


    if(pos < 0)
    {
        return false;
    }


    command = message.substring(
        0,
        pos
    );


    data = message.substring(
        pos + 1
    );


    data.trim();


    return true;

}
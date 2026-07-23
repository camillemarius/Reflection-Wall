#ifndef TEXT_STORAGE_H
#define TEXT_STORAGE_H

#include <Arduino.h>


class TextStorage
{

public:

    bool begin();

    bool save(
        String text
    );

    String load();

    bool exists();

    bool clear();


private:

    const char* filename =
        "/text.txt";

};


#endif
#include "textStorage.h"
#include <LittleFS.h>



bool TextStorage::begin()
{

    return LittleFS.begin();

}



bool TextStorage::save(String text) {

    File file = LittleFS.open(filename,"w");
    if(!file) {
        return false;
    }


    file.print(
        text
    );


    file.close();


    return true;

}



String TextStorage::load()
{

    File file = LittleFS.open(
        filename,
        "r"
    );


    if(!file)
    {
        return "";
    }


    String text =
        file.readString();


    file.close();


    return text;

}



bool TextStorage::exists()
{
    return LittleFS.exists(
        filename
    );
}



bool TextStorage::clear()
{

    return LittleFS.remove(
        filename
    );

}
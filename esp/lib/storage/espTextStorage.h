#pragma once

#include <Arduino.h>
#include <LittleFS.h>

#include "ITextStorage.h"

class EspTextStorage : public ITextStorage
{
public:
    bool begin() override;

    bool writeText(const String& text) override;

    String readText() override;

    void clear() override;

private:
    const char* FILE_NAME = "/text.txt";
};
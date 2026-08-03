#pragma once

#include <Arduino.h>

class ITextStorage
{
public:
    virtual ~ITextStorage() = default;

    virtual bool begin() = 0;

    virtual bool writeText(const String& text) = 0;

    virtual String readText() = 0;

    virtual void clear() = 0;
};
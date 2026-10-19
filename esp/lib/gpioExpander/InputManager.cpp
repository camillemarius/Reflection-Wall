#include "InputManager.h"

namespace
{
    // Voreinstellung der Sperrzeit gegen Prellen. Gilt nur
    // fuer Flanken - Pegel sollen bewusst wiederholt ausloesen.
    constexpr unsigned long DEFAULT_DEBOUNCE_MS = 250;
}


InputManager::InputManager(PCF8575& expander)
    : _expander(expander),
      _debounceMs(DEFAULT_DEBOUNCE_MS)
{
    for (uint8_t i = 0; i < BUTTON_COUNT; i++)
    {
        _triggers[i] = InputTrigger::NONE;
        _lastFire[i] = 0;
    }
}


void InputManager::begin()
{
    _expander.read16();
}


// ---------------------------------------------------------
// Zuordnung Taster <-> Expander-Pin
// ---------------------------------------------------------
// Von unten nach oben: B1 auf P03 ... B6 auf P10

uint8_t InputManager::pinFor(InputEvent button)
{
    switch(button)
    {
        case InputEvent::BT1: return 3;
        case InputEvent::BT2: return 4;
        case InputEvent::BT3: return 5;
        case InputEvent::BT4: return 8;
        case InputEvent::BT5: return 9;
        case InputEvent::BT6: return 10;

        default:
            return 0xFF;
    }
}

uint8_t InputManager::indexFor(InputEvent button)
{
    switch(button)
    {
        case InputEvent::BT1: return 0;
        case InputEvent::BT2: return 1;
        case InputEvent::BT3: return 2;
        case InputEvent::BT4: return 3;
        case InputEvent::BT5: return 4;
        case InputEvent::BT6: return 5;

        default:
            return 0xFF;
    }
}

InputEvent InputManager::buttonAt(uint8_t index)
{
    switch(index)
    {
        case 0: return InputEvent::BT1;
        case 1: return InputEvent::BT2;
        case 2: return InputEvent::BT3;
        case 3: return InputEvent::BT4;
        case 4: return InputEvent::BT5;
        case 5: return InputEvent::BT6;

        default:
            return InputEvent::NONE;
    }
}


// ---------------------------------------------------------
// Zustandsabfragen
// ---------------------------------------------------------

InputEvent InputManager::getEvent()
{
    const uint16_t state = _expander.read16();

    for (uint8_t i = 0; i < BUTTON_COUNT; i++)
    {
        const InputEvent button = buttonAt(i);

        if (isPressed(button, state))
            return button;
    }

    return InputEvent::NONE;
}

bool InputManager::getButtonState(InputEvent button)
{
    const uint8_t pin = pinFor(button);

    if (pin == 0xFF)
        return true;

    const uint16_t state = _expander.read16();

    return (state & (1 << pin)) != 0;
}

// LOW = Taster gedrueckt
bool InputManager::isPressed(InputEvent button, uint16_t state) const
{
    const uint8_t pin = pinFor(button);

    if (pin == 0xFF)
        return false;

    return (state & (1 << pin)) == 0;
}


// ---------------------------------------------------------
// Trigger-Konfiguration
// ---------------------------------------------------------

void InputManager::setTrigger(InputEvent button, InputTrigger trigger)
{
    const uint8_t index = indexFor(button);

    if (index == 0xFF)
        return;

    _triggers[index] = trigger;
}

InputTrigger InputManager::getTrigger(InputEvent button) const
{
    const uint8_t index = indexFor(button);

    if (index == 0xFF)
        return InputTrigger::NONE;

    return _triggers[index];
}

void InputManager::setDebounceMs(unsigned long milliseconds)
{
    _debounceMs = milliseconds;
}


bool InputManager::matches(InputTrigger trigger, bool wasHigh, bool isHigh)
{
    switch (trigger)
    {
        case InputTrigger::RISING_EDGE:  return !wasHigh && isHigh;
        case InputTrigger::FALLING_EDGE: return wasHigh && !isHigh;
        case InputTrigger::LEVEL_HIGH:   return isHigh;
        case InputTrigger::LEVEL_LOW:    return !isHigh;

        default:
            return false;
    }
}


// ---------------------------------------------------------
// Auswertung
// ---------------------------------------------------------

uint8_t InputManager::collectEvents(uint16_t previous,
                                    uint16_t current,
                                    InputEvent* events,
                                    uint8_t maxEvents)
{
    if (events == nullptr)
        return 0;

    const unsigned long now = millis();

    uint8_t count = 0;

    for (uint8_t i = 0; i < BUTTON_COUNT && count < maxEvents; i++)
    {
        const InputTrigger trigger = _triggers[i];

        if (trigger == InputTrigger::NONE)
            continue;

        const uint8_t pin = pinFor(buttonAt(i));

        if (pin == 0xFF)
            continue;

        const bool wasHigh = (previous & (1 << pin)) != 0;
        const bool isHigh  = (current  & (1 << pin)) != 0;

        if (!matches(trigger, wasHigh, isHigh))
            continue;

        // Nur Flanken entprellen. Pegel sollen wiederholt
        // ausloesen, solange der Zustand anliegt.
        const bool isEdge = trigger == InputTrigger::RISING_EDGE
                         || trigger == InputTrigger::FALLING_EDGE;

        if (isEdge && _debounceMs > 0 && (now - _lastFire[i]) < _debounceMs)
            continue;

        _lastFire[i] = now;

        events[count] = buttonAt(i);
        count++;
    }

    return count;
}


// ---------------------------------------------------------
// LEDs
// ---------------------------------------------------------

void InputManager::setLed(InputEvent button, bool on)
{
    uint8_t pin = 0;

    switch (button)
    {
        case InputEvent::BT1: pin = 2;  break;
        case InputEvent::BT2: pin = 1;  break;
        case InputEvent::BT3: pin = 0;  break;
        case InputEvent::BT4: pin = 15; break;
        case InputEvent::BT5: pin = 14; break;
        case InputEvent::BT6: pin = 13; break;
        default: return;
    }

    // LED aktiv LOW
    _expander.setOutput(pin, !on);
}

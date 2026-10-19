#pragma once

#include "PCF8575.h"
#include "InputEvent.h"

class InputManager
{
public:

    static constexpr uint8_t BUTTON_COUNT = 6;

    InputManager(PCF8575& expander);

    void begin();
    void setLed(InputEvent button, bool on);

    InputEvent getEvent();
    bool getButtonState(InputEvent button);

    // Auswertung eines bereits gelesenen Registerwerts,
    // ohne erneuten Buszugriff
    bool isPressed(InputEvent button, uint16_t state) const;

    // Konfiguration, wann ein Taster eine Aktion ausloest
    void setTrigger(InputEvent button, InputTrigger trigger);
    InputTrigger getTrigger(InputEvent button) const;

    // Sperrzeit gegen Prellen, in Millisekunden.
    //
    // Sinnvoll nur, solange derselbe InputManager mehrere
    // Lesevorgaenge erlebt. Startet der ESP fuer jeden
    // Tastendruck neu, ist _lastFire[] immer 0 und millis()
    // immer klein: der Filter wuerde dann jeden ersten Event
    // verschlucken statt zu entprellen. In dem Fall 0 setzen -
    // die Bootzeit selbst ist laenger als jedes Prellen.
    void setDebounceMs(unsigned long milliseconds);

    // Vergleicht zwei Registerwerte und sammelt alle Taster,
    // deren konfigurierte Bedingung erfuellt ist. Rueckgabe ist
    // die Anzahl der Eintraege in events[].
    uint8_t collectEvents(uint16_t previous,
                          uint16_t current,
                          InputEvent* events,
                          uint8_t maxEvents);


private:

    static uint8_t pinFor(InputEvent button);
    static uint8_t indexFor(InputEvent button);
    static InputEvent buttonAt(uint8_t index);

    static bool matches(InputTrigger trigger, bool wasHigh, bool isHigh);

    PCF8575& _expander;

    InputTrigger _triggers[BUTTON_COUNT];
    unsigned long _lastFire[BUTTON_COUNT];
    unsigned long _debounceMs;
};

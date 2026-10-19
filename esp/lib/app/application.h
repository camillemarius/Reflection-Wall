#pragma once

#include "UartHandler.h"
#include "TextStorage.h"
#include "Display.h"
#include "PiCommunication.h"
#include "WakeupReason.h"
#include "PersistentState.h"

#include "PCF8575.h"
#include "InputManager.h"
#include "WifiController.h"

// ---------------------------------------------------------
// Ablauf
// ---------------------------------------------------------
// Es gibt keine Hauptschleife mehr. Die Hardware weckt den
// ESP ueber den INT-Ausgang des GPIO Expanders, der auf RST
// geht: jede Aenderung an einem Taster ist damit ein Reset.
//
// run() laeuft genau einmal durch - Zustand lesen, Taster
// auswerten, reagieren, Zustand sichern - und geht am Ende in
// den Deep Sleep. Die Funktion kehrt nicht zurueck.
//
// Alles, was ueber einen Tastendruck hinaus bestehen bleiben
// muss, liegt in PersistentState im RTC-Speicher. Objekt-
// zustand im RAM ist nach dem Reset weg.

class Application
{
public:
    Application();

    // Laeuft einmal komplett durch und schlaeft dann ein.
    // Kehrt nicht zurueck.
    void run();

private:
    void togglePowerSwitch();
    void configurePowerSwitchPin();

    // Liest den Expander und gibt damit die INT-Leitung frei
    uint16_t readExpander();

    // Initialisiert die Anzeige beim ersten Zugriff in diesem
    // Durchlauf. Nach einem reinen Tastendruck ohne Textwechsel
    // wird die Anzeige gar nicht angefasst - die HT16K33
    // behalten ihren Inhalt ueber den Reset hinweg.
    void ensureDisplayReady();

    // Zentrale Zuweisung Taster -> Aktion
    void handleInput(InputEvent button);

    // Zeigt den Text aus dem Flash (TextStorage)
    void showText();

    void enterDeepSleep();

    UartHandler _uart;
    TextStorage _storage;
    Display _display;
    piCommunication _pi;

    PCF8575 _gpioExpander;
    InputManager _inputs;

    WakeupReason::Reason _wakeupReason;

    WifiController _wifi;

    // Ueberlebt den Reset im RTC-Speicher
    PersistentState::Data _state;

    // true, wenn der RTC-Speicher leer war: die Spannung war
    // weg, die Anzeige ist uninitialisiert.
    bool _coldBoot;

    // Wurde _display.begin() in diesem Durchlauf schon
    // aufgerufen?
    bool _displayReady;

    // rpi Power Switch (Clock-Puls auf das Flipflop)
    uint8_t _pulseIdle;
};

#pragma once

#include "display.h"
#include "wakeupReason.h"
#include "features.h"
#include "PersistentState.h"
#include "LittleFsAdapter.h"
#include "QuoteStore.h"
#include "FramQuoteStore.h"
#include "FramBus.h"
#include "WallLogic.h"
#include "PiPower.h"
#include "PowerSwitchPin.h"
#include "UartPort.h"
#include "PiLink.h"

#include "PCF8575.h"
#include "InputManager.h"

// ---------------------------------------------------------
// Ablauf
// ---------------------------------------------------------
// Es gibt keine Hauptschleife mehr. Die Hardware weckt den
// ESP ueber den INT-Ausgang des GPIO Expanders, der auf RST
// geht: jede Aenderung an einem Taster ist damit ein Reset.
//
// run() laeuft einmal durch - Zustand lesen, Taster und Radar
// auswerten, reagieren, Zustand sichern - und geht am Ende in
// den Deep Sleep. Solange die Wand an ist, bleibt run() wach und
// liest den Radar (runWallLoop), bevor es schlafen geht. Die
// Funktion kehrt nicht zurueck. Auch der Radar (INT_HLK) weckt
// den ESP, nicht nur die Taster.
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
    // Liest den Expander und gibt damit die INT-Leitung frei
    uint16_t readExpander();

    // Initialisiert die Anzeige beim ersten Zugriff in diesem
    // Durchlauf. Nach einem reinen Tastendruck ohne Textwechsel
    // wird die Anzeige gar nicht angefasst - die HT16K33
    // behalten ihren Inhalt ueber den Reset hinweg.
    void ensureDisplayReady();

    // Zentrale Zuweisung Taster -> Aktion
    void handleInput(InputEvent button);

    // Zeigt ein Zitat aus der Liste im FRAM; welches, bestimmt
    // die Aktion (neuestes, aktuelles, naechstes)
    void showQuote(WallAction action);

    // Bleibt wach, solange die Wand an ist, und schaltet sie
    // ab, sobald die Regeln es verlangen
    void runWallLoop();

    // Anzeige dunkel schalten und den Zustand nachfuehren
    void turnWallOff();

    void enterDeepSleep();

    // Radar meldet "jemand da"? Liest INT_HLK nur, wenn der Radar
    // eingebaut ist (Features::RADAR_INSTALLED)
    bool radarHigh();

    Display _display;

    // Der aktive Zitatspeicher: FRAM oder Flash, je nach Features::FRAM_INSTALLED
    IQuoteStore& quotes();

    // Reihenfolge: die Speicher halten Referenzen auf _fs bzw. _framBus
    LittleFsAdapter _fs;
    FramBus _framBus;
    QuoteStore _flashQuotes;
    FramQuoteStore _framQuotes;

    PCF8575 _gpioExpander;
    InputManager _inputs;

    WakeupReason::Reason _wakeupReason;

    // Ueberlebt den Reset im RTC-Speicher
    PersistentState::Data _state;

    // true, wenn der RTC-Speicher leer war: die Spannung war
    // weg, die Anzeige ist uninitialisiert.
    bool _coldBoot;

    // Wurde _display.begin() in diesem Durchlauf schon
    // aufgerufen?
    bool _displayReady;

    // Pi-Speisung (Clock-Puls auf das Flipflop); Reihenfolge: _piPower haelt eine Referenz auf _powerPin
    PowerSwitchPin _powerPin;
    PiPower _piPower;

    // Verbindung zum Pi; Reihenfolge: _link haelt eine Referenz auf _port
    UartPort _port;
    PiLink _link;

    // BT3 wurde in diesem Durchlauf gedrueckt: Verbindungstest nach dem Sichern des Tastenstands
    bool _linkTestRequested;
};

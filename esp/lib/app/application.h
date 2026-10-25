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
#include "PiSession.h"

#include "PCF8575.h"
#include "InputManager.h"

#include <string>
#include <vector>

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
// Laeuft eine Sitzung mit dem Pi (PiSession), bleibt run() wach,
// bis sie zu Ende ist (runSession). Ein Reset mittendrin macht
// im selben Zustand weiter; die Wand-Regeln ruhen so lange.
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

    // Zentrale Zuweisung Taster -> Aktion. Was die Sitzung daraus
    // macht, landet in actions.
    void handleInput(InputEvent button, std::vector<SessionAction>& actions);

    // Bleibt wach, solange die Sitzung aktiv ist: Leitung lesen,
    // Takt, Aktionen ausfuehren, Zustand sichern
    void runSession(std::vector<SessionAction>& actions);

    // Fuehrt die Aktionen der Sitzung der Reihe nach aus und
    // leert die Liste
    void executeActions(std::vector<SessionAction>& actions);

    // Anzeigetexte der Sitzung (PI STARTET ...) und Anzeige aus
    void showSessionText(const std::string& text);
    void sessionDisplayOff();

    // Nummern der Verbindung in _state uebernehmen und sichern
    void saveState();

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

    // Sitzung mit dem Pi; ihr Zustand liegt in _state.session
    // (Reihenfolge: nach _state)
    PiSession _session;

    // BT3 ohne Sitzung in diesem Durchlauf: Verbindungstest nach dem Sichern des Tastenstands
    bool _linkTestRequested;
};

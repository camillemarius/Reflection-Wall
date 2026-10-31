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
#include "WakePlan.h"
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
// Dazu weckt der Timer (GPIO16 -> RST): Jede Schlafstrecke
// endet spaetestens nach 3 h oder am naechsten Termin der
// Nacht (WakePlan).
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
// im selben Zustand weiter. In einer Sitzung HAND ruhen die
// Wand-Regeln, in einer Sitzung NACHT laufen sie mit (N2).
//
// Am Ende jedes Durchlaufs, und wach jede Sekunde, entscheidet
// WakePlan nach der Uhr: abgleichen, mit Funk neu starten, den
// Auftrag der Nacht beginnen oder schlafen.
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
    // Ergebnis von beginNightAttempt
    enum class NightStart
    {
        Started,  // Auftrag laeuft (Wanted), mit neuer oder laufender Sitzung
        Skipped,  // Termin verbraucht ohne Pi (Zitat der letzten Nacht nicht gespeichert)
        Ignored   // nichts geaendert: GET laeuft, Zitat da oder die Sitzung nimmt keinen Auftrag
    };

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
    // Takt, Aktionen ausfuehren, Zustand sichern. In der Nacht
    // dazu die Wand-Regeln (N2), jede Sekunde der Weckplan.
    void runSession(std::vector<SessionAction>& actions);

    // Fuehrt die Aktionen der Sitzung der Reihe nach aus und
    // leert die Liste
    void executeActions(std::vector<SessionAction>& actions);

    // Anzeigetexte der Sitzung (PI STARTET ...) und Anzeige aus
    void showSessionText(const std::string& text);
    void sessionDisplayOff();

    // Uhr nachfuehren, Nummern der Verbindung in _state
    // uebernehmen und sichern
    void saveState();

    // Zaehlt die wach verbrachte Zeit seit dem letzten Aufruf zur Uhr
    void advanceClock();

    // Zeigt ein Zitat aus der Liste im FRAM; welches, bestimmt
    // die Aktion (neuestes, aktuelles, naechstes)
    void showQuote(WallAction action);

    // Schreibt ein Zitat auf die Anzeige und merkt sich, welches
    // (Index, Datum), mit displayState = Writing davor
    void writeQuote(const std::string& text, std::size_t index, const std::string& date);

    // Wand-Regeln beim Start (decideOnBoot): BT1, Radar, abgebrochenes Schreiben
    void wallOnBoot(bool button1);

    // Bleibt wach, solange die Wand an ist, und schaltet sie
    // ab, sobald die Regeln es verlangen. Kehrt auch zurueck,
    // wenn der Auftrag der Nacht eine Sitzung gestartet hat (Z11).
    void runWallLoop(std::vector<SessionAction>& actions);

    // Anzeige dunkel schalten und den Zustand nachfuehren
    void turnWallOff();

    // Radar meldet "jemand da"? Liest INT_HLK nur, wenn der Radar
    // eingebaut ist (Features::RADAR_INSTALLED)
    bool radarHigh();

    // -----------------------------------------------------
    // Uhr und Nacht
    // -----------------------------------------------------

    // WakePlan::decide mit aktueller Uhr. SyncNow und
    // RestartWithRadio fuehrt es selbst aus; zurueck kommt
    // Sleep oder StartNight. In einer Sitzung, in der der Abgleich
    // nichts nuetzt (syncWaitsForSession), kommt SyncNow oder
    // RestartWithRadio unausgefuehrt zurueck und heisst "weiter".
    WakeDecision plan();

    // In einer Sitzung lohnt der Abgleich nur, wenn die Uhr gilt und
    // die Sitzung den Auftrag danach annaehme. Sonst wartet er bis
    // nach der Sitzung. Ohne Sitzung false.
    bool syncWaitsForSession();

    // NTP-Abgleich (SyncNow); nach einem Kaltstart ohne Zugangsdaten
    // zuerst das Portal. Scheitert er, gilt _syncFailed.
    void syncClock();

    // StartNight: Versuch beginnen, ohne Sitzung mit Pi ein (NACHT)
    NightStart beginNightAttempt(std::vector<SessionAction>& actions);

    // Nach einem Kaltstart die Liste einmal lesen; ein Zitat, das
    // noch nicht in der Liste steht, nachtragen. Nur ohne Sitzung.
    void catchUpNight();

    // Zitat der Nacht vorne in die Liste (P1-a). true: steht dort.
    bool writePendingQuote();

    // Liste laden und loggen; erneuert night.yesterday (R6)
    QuoteList loadQuotes();

    // Darf die Liste jetzt gelesen werden? Nur mit dem Pi aus oder
    // in einer Sitzung NACHT (R6, R14 aus Teil 2).
    bool listAllowed() const;

    // Sitzung NACHT laeuft (nicht AUS)
    bool nightSession() const;

    // Uhr, Auftrag und Ergebnis der Nacht ins Log
    void logClock(const char* what);
    void logNight();

    // R3: 1 ms schlafen mit Funk; kehrt nicht zurueck
    void restartWithRadio();

    // Timer-Schlaf; kehrt nicht zurueck
    void enterDeepSleep(uint32_t sleepS, bool radio);

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
    // und _state.night (Reihenfolge: nach _state)
    PiSession _session;

    // BT3 ohne Sitzung in diesem Durchlauf: Verbindungstest nach dem Sichern des Tastenstands
    bool _linkTestRequested;

    // Dieser Durchlauf hat Funk: Kaltstart, oder die letzte
    // Schlafstrecke war mit Funk geplant (clock.radio)
    bool _radioOn;

    // Ein Abgleich ist in diesem Durchlauf gescheitert (R16)
    bool _syncFailed;

    // Dieser Durchlauf begann vor der Zeit (Taste, Reset) und ist
    // kein Kaltstart: ohne Uhr gleicht er nicht ab (WakePlan::decide)
    bool _earlyWake;

    // Das Portal lief in diesem Durchlauf schon
    bool _portalDone;

    // Dateisystem in diesem Durchlauf eingebunden
    bool _fsReady;

    // Die Liste wurde in diesem Durchlauf gelesen; yesterday ist aktuell
    bool _listRead;

    // Schritt 3 (Liste nach dem Kaltstart) ist erledigt
    bool _coldListDone;

    // Steht in diesem Durchlauf schon im Log: "Auftrag wartet bis
    // nach der Sitzung", "Sitzung nimmt keinen an", "Abgleich wartet"
    bool _nightWaitLogged;
    bool _refusedLogged;
    bool _syncWaitLogged;

    // millis() beim letzten Nachfuehren der Uhr
    unsigned long _clockMs;

    // millis(), ab dem die Fristen der Sitzung zaehlen: 0 fuer eine
    // Sitzung vom Start dieses Durchlaufs (R1), sonst ihr Beginn
    unsigned long _sessionSinceMs;
};

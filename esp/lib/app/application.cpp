#include "Application.h"
#include "I2CMasterControl.h"
#include "pinMapping.h"

#include "DebugLogger.h"
#include "BufferTest.h"

#include <ESP8266WiFi.h>

Application::Application()
    : _uart(Serial),
      _storage(),
      _display(),
      _pi(_uart, _storage, _display),
      _fs(),
      _quotes(_fs),
      _gpioExpander(0x20),
      _inputs(_gpioExpander),
      _wakeupReason(WakeupReason::Reason::UNKNOWN),
      _wifi(),
      _state(),
      _coldBoot(false),
      _displayReady(false),
      _pulseIdle(HIGH)
{
}

namespace
{
    // Die Zitate stehen in /quotes.txt im LittleFS (QuoteStore).
    // Fehlt die Datei oder ist sie leer, zeigt die Wand diesen
    // Hinweis statt dunkel zu bleiben.
    constexpr char NO_TEXT[] = "KEIN TEXT";

    // 12 Module x 8 Zeichen
    constexpr unsigned int DISPLAY_CHARS = 96;

    const char* buttonName(InputEvent button)
    {
        switch (button)
        {
            case InputEvent::BT1: return "BT1";
            case InputEvent::BT2: return "BT2";
            case InputEvent::BT3: return "BT3";
            case InputEvent::BT4: return "BT4";
            case InputEvent::BT5: return "BT5";
            case InputEvent::BT6: return "BT6";
            default: return "?";
        }
    }

    // So oft liest die Wand den Radar, solange sie an ist. Das
    // Delay fuettert zugleich den Watchdog.
    constexpr unsigned long WALL_POLL_MS = 200;

    const char* actionName(WallAction action)
    {
        switch (action)
        {
            case WallAction::ShowNewest: return "neuestes";
            case WallAction::ShowNext: return "naechstes";
            case WallAction::ShowCurrent: return "aktuelles";
            default: return "keine";
        }
    }

    // Breite des Clock-Pulses fuer das Flipflop am Relais
    constexpr unsigned long PULSE_MS = 50;

    // Beim Aufwachen bleibt das Funkteil aus: es kostet rund
    // 70 mA und etwa 200 ms Bootzeit, die hier niemand braucht.
    // Fuer OTA muss dieser Wert auf WAKE_RF_DEFAULT stehen -
    // die Einstellung wird im RTC-Speicher hinterlegt und gilt
    // erst ab dem naechsten Start.
    constexpr RFMode WAKE_RF_MODE = WAKE_RF_DISABLED;

    // Abnahmetest fuer den I2C-Buffer (PCA9517A), siehe
    // BufferTest.h. Laeuft endlos statt in den Deep Sleep.
    // Fuer den Normalbetrieb auf false.
    constexpr bool BUFFER_TEST = false;
}

// ---------------------------------------------------------
// Application::run()
// ---------------------------------------------------------
// Ein Durchlauf pro Tastendruck. Die Reihenfolge ist nicht
// beliebig:
//
//   1. Funk aus, bevor irgendetwas Strom zieht
//   2. Weckgrund lesen, solange INT noch anliegt
//   3. Expander lesen - moeglichst frueh, weil der Taster
//      nur so lange lesbar ist, wie er gedrueckt wird
//   4. erst danach alles, was Zeit kostet: Ausgaben, Anzeige

void Application::run()
{
    // -----------------------------------------------------
    // 1. Funk
    // -----------------------------------------------------
    // WAKE_RF_MODE haelt das Funkteil beim Aufwachen schon aus.
    // Beim Kaltstart greift das nicht - die Einstellung liegt
    // im RTC-Speicher und ist mit der Spannung weg. Dann zieht
    // der ESP die Betriebsart aus dem Flash und faehrt WLAN
    // hoch, deshalb hier zusaetzlich explizit abschalten.
    //
    // persistent(false) ist dabei Pflicht: sonst schreibt jedes
    // WiFi.mode() die Betriebsart ins Flash zurueck - bei einem
    // Boot pro Tastendruck waere der Sektor absehbar durch.

    WiFi.persistent(false);
    WiFi.mode(WIFI_OFF);
    WiFi.forceSleepBegin();

    DebugSerial.begin(74880);  // same baud as the ESP8266 boot ROM -> boot log readable

    // -----------------------------------------------------
    // 2. Weckgrund
    // -----------------------------------------------------
    // Muss vor dem Expander-Lesevorgang passieren: das Lesen
    // gibt die INT-Leitung frei und loescht damit den Hinweis
    // darauf, wer den Reset ausgeloest hat.

    _wakeupReason = WakeupReason::getReason();

    // -----------------------------------------------------
    // 3. Zustand aus dem RTC-Speicher
    // -----------------------------------------------------

    _coldBoot = !PersistentState::load(_state);

    _state.wakeCount++;

    // -----------------------------------------------------
    // 4. Expander lesen und auswerten
    // -----------------------------------------------------

    I2CMasterControl::begin();

    if (BUFFER_TEST)
        BufferTest::run();

    const uint16_t state = readExpander();

    // Ohne die Schleife entprellt nichts mehr ueber die Zeit -
    // der Reset selbst trennt die Ereignisse, und millis()
    // faengt bei jedem Durchlauf neu an.
    _inputs.setDebounceMs(0);

    // BT1-BT3 laufen ueber Toggle-Flipflops (Blatt "Button
    // Debouncing"): jeder Druck kippt den Pegel, und der neue
    // Pegel bleibt stehen, bis der ESP ihn liest. Ein Wechsel
    // ist deshalb genau ein Druck, egal wie kurz er war.
    //
    // BT4-BT6 haengen direkt am Expander. Der ESP sieht sie nur,
    // solange sie beim Lesen noch gedrueckt sind - ein kurzer
    // Druck ist vorbei, bevor der ESP nach dem Reset liest.
    // Deshalb loesen sie nichts aus.
    _inputs.setTrigger(InputEvent::BT1, InputTrigger::ANY_EDGE);
    _inputs.setTrigger(InputEvent::BT2, InputTrigger::ANY_EDGE);
    _inputs.setTrigger(InputEvent::BT3, InputTrigger::NONE);
    _inputs.setTrigger(InputEvent::BT4, InputTrigger::NONE);
    _inputs.setTrigger(InputEvent::BT5, InputTrigger::NONE);
    _inputs.setTrigger(InputEvent::BT6, InputTrigger::NONE);

    // Beim Kaltstart ist der vorherige Pegel unbekannt. Statt
    // 0xFFFF anzunehmen und damit jeden zufaellig gehaltenen
    // Taster als frischen Druck zu melden, wird der gelesene
    // Wert als Referenz gesetzt: nach dem Einschalten loest
    // kein Taster aus.
    if (_coldBoot)
        _state.lastExpanderState = state;

    InputEvent events[InputManager::BUTTON_COUNT];

    const uint8_t count = _inputs.collectEvents(_state.lastExpanderState,
                                                state,
                                                events,
                                                InputManager::BUTTON_COUNT);

    _state.lastExpanderState = state;

    // -----------------------------------------------------
    // 5. Ab hier darf es dauern
    // -----------------------------------------------------

    DebugSerial.printf("\n=== REFLECTION WALL (Wakeup #%lu%s) ===\n",
                       (unsigned long)_state.wakeCount,
                       _coldBoot ? ", Kaltstart" : "");

    WakeupReason::log(_wakeupReason);

    DebugSerial.printf("[INPUT] Expander 0x%02X = 0x%04X, %u Event(s)\n",
                       _gpioExpander.getAddress(),
                       state,
                       count);

    // Nach dem Einschalten bleibt die Wand dunkel, bis der
    // Radar oder BT1 sie einschaltet.
    bool button1 = false;

    for (uint8_t i = 0; i < count; i++)
    {
        DebugSerial.printf("[INPUT] %s -> ", buttonName(events[i]));

        if (events[i] == InputEvent::BT1)
            button1 = true;

        handleInput(events[i]);
    }

    // Was die Wand zeigt, entscheiden die Wand-Regeln
    const bool radarHigh = digitalRead(Pins::INT_HLK) == HIGH;

    WallBoot boot;
    boot.displayOn = _state.displayState != 0;
    boot.displayWriting = _state.displayState == 2;
    boot.radarHigh = radarHigh;
    boot.button1 = button1;

    const WallAction action = decideOnBoot(boot);

    if (button1)
        _state.button1Active = 1;

    if (action != WallAction::None)
        showQuote(action);

    if (_state.displayState == 1)
        runWallLoop();

    // -----------------------------------------------------
    // 6. Zustand sichern und schlafen
    // -----------------------------------------------------

    PersistentState::save(_state);

    enterDeepSleep();
}

// ---------------------------------------------------------
// rpi Power Switch
// ---------------------------------------------------------
// GPIO12 taktet ein Flipflop, das den Relaiszustand auch ohne
// den ESP haelt. Der Ruhepegel wird gemessen statt angenommen:
// uebernimmt der Pin beim Wechsel auf Ausgang exakt den Pegel,
// den die Leitung ohnehin fuehrt, entsteht keine Flanke und
// das Relais bleibt unberuehrt.
//
// Aufgerufen wird das nur aus togglePowerSwitch(), also nur
// dann, wenn BT5 tatsaechlich gedrueckt wurde. In jedem
// anderen Durchlauf bleibt GPIO12 Eingang und damit hochohmig:
// der ESP haengt sich nicht bei jedem Boot an die Taktleitung
// des Flipflops.

void Application::configurePowerSwitchPin()
{
    pinMode(Pins::ESP_GPIO12_PS, INPUT);
    _pulseIdle = digitalRead(Pins::ESP_GPIO12_PS);

    // digitalWrite() setzt beim ESP8266 das Ausgangsregister
    // schon im Eingangsmodus. In der umgekehrten Reihenfolge
    // wuerde pinMode(OUTPUT) den Pin kurz auf LOW ziehen.
    digitalWrite(Pins::ESP_GPIO12_PS, _pulseIdle);
    pinMode(Pins::ESP_GPIO12_PS, OUTPUT);
}

// Ein Puls gegen den Ruhepegel kippt das Flipflop. Den
// resultierenden Relaiszustand kennt der ESP nicht - er liegt
// im Flipflop und ueberlebt auch dessen Stromausfall.
//
// Der Pin wird erst hier eingerichtet - vorher ist er Eingang.

void Application::togglePowerSwitch()
{
    configurePowerSwitchPin();

    digitalWrite(Pins::ESP_GPIO12_PS, _pulseIdle ? LOW : HIGH);
    delay(PULSE_MS);
    digitalWrite(Pins::ESP_GPIO12_PS, _pulseIdle);
}

// ---------------------------------------------------------
// Expander lesen
// ---------------------------------------------------------
// Der Lesevorgang gibt zugleich die INT-Leitung wieder frei.
// Bleibt er aus, haelt der Expander INT auf LOW und der ESP
// kaeme aus dem Reset nicht mehr heraus. Deshalb wird in jedem
// Durchlauf gelesen, auch wenn sich daraus kein Event ergibt.
//
// Jeder Buszugriff wird mit enable()/disable() geklammert,
// damit der andere Master den Bus dazwischen wieder bekommt.

uint16_t Application::readExpander()
{
    I2CMasterControl::enable();

    _gpioExpander.begin();

    // Ohne Expander gibt es keine Tasterereignisse. read16()
    // liefert dann 0xFFFF - ununterscheidbar von "keine Taste
    // gedrueckt". Deshalb hier explizit pruefen und melden.
    const bool expanderOk = _gpioExpander.isConnected();

    const uint16_t state = _gpioExpander.read16();

    I2CMasterControl::disable();

    if (!expanderOk)
        DebugSerial.printf("[INPUT] FEHLER: GPIO Expander 0x%02X antwortet nicht\n",
                           _gpioExpander.getAddress());

    return state;
}

// ---------------------------------------------------------
// Anzeige
// ---------------------------------------------------------
// begin() kostet ueber ein Dutzend Buszugriffe. Sie lohnen
// sich nur, wenn tatsaechlich etwas geschrieben wird - ein
// Druck auf BT5 laesst die Anzeige unberuehrt.

void Application::ensureDisplayReady()
{
    if (_displayReady)
        return;

    _display.begin();

    _displayReady = true;
}

// Das Zitat bleibt stehen, bis etwas anderes geschrieben wird -
// die HT16K33 halten ihren Inhalt selbst, auch ueber einen
// Reset des ESP hinweg.
//
// Das Dateisystem wird erst hier eingebunden, also nur in
// Durchlaeufen, die tatsaechlich etwas anzeigen.
//
// displayState = 2 steht im RTC-Speicher, bevor die Module
// beschrieben werden: bricht der Durchlauf dabei ab, schreibt
// der naechste das Zitat neu.

void Application::showQuote(WallAction action)
{
    if (!_fs.begin())
        DebugSerial.println("[WALL] FEHLER: Dateisystem laesst sich nicht einbinden");

    const QuoteList list = _quotes.load();

    std::string text;
    std::string date;
    std::size_t index = 0;

    if (list.empty())
    {
        DebugSerial.println("[WALL] FEHLER: kein Zitat im Flash");
        text = NO_TEXT;
    }
    else
    {
        const std::string shownDate(_state.shownDate);

        switch (action)
        {
            case WallAction::ShowNewest:
                index = 0;
                break;

            case WallAction::ShowNext:
                index = list.nextIndex(list.resolveIndex(_state.shownIndex, shownDate));
                break;

            default:
                index = list.resolveIndex(_state.shownIndex, shownDate);
                break;
        }

        text = list.at(index).text;
        date = list.at(index).date;
    }

    if (text.length() > DISPLAY_CHARS)
        DebugSerial.printf("[TEXT] Warnung: %u Zeichen, die Anzeige fasst %u\n",
                           (unsigned)text.length(), DISPLAY_CHARS);

    DebugSerial.printf("[WALL] %s -> #%u %s \"%s\"\n",
                       actionName(action),
                       (unsigned)index,
                       date.c_str(),
                       text.c_str());

    _state.displayState = 2;
    PersistentState::save(_state);

    ensureDisplayReady();
    _display.show(String(text.c_str()));

    // Index und Datum merken: das Datum findet den Eintrag
    // wieder, falls die Liste sich verschiebt
    _state.displayState = 1;
    _state.shownIndex = static_cast<uint8_t>(index);
    memset(_state.shownDate, 0, sizeof(_state.shownDate));
    strncpy(_state.shownDate, date.c_str(), sizeof(_state.shownDate) - 1);

    PersistentState::save(_state);
}

// ---------------------------------------------------------
// Wand an
// ---------------------------------------------------------
// Der ESP bleibt wach und prueft den Radar, bis die Regeln
// das Abschalten verlangen. millis() zaehlt ab dem Start
// dieses Durchlaufs.

void Application::runWallLoop()
{
    while (true)
    {
        delay(WALL_POLL_MS);

        const bool radarHigh = digitalRead(Pins::INT_HLK) == HIGH;

        if (wallShouldTurnOff(radarHigh, _state.button1Active != 0, millis()))
        {
            turnWallOff();
            return;
        }
    }
}

void Application::turnWallOff()
{
    _display.setPower(false);

    _state.displayState = 0;
    _state.button1Active = 0;

    PersistentState::save(_state);

    DebugSerial.println("[WALL] aus");
}

// ---------------------------------------------------------
// Zuweisung Taster -> Aktion
// ---------------------------------------------------------
// Welcher Taster hier ankommt, bestimmt die Trigger-
// Konfiguration in run(). Steht ein Taster auf NONE, wird
// sein Zweig nie erreicht.

void Application::handleInput(InputEvent button)
{
    switch (button)
    {
        case InputEvent::BT1:
            DebugSerial.println("ueber die Wand-Regeln");
            break;

        case InputEvent::BT2:
            DebugSerial.println("Power Switch umschalten");
            togglePowerSwitch();
            break;

        case InputEvent::BT3:
            DebugSerial.println("(keine Aktion)");
            break;

        case InputEvent::BT4:
            DebugSerial.println("(keine Aktion)");
            break;

        case InputEvent::BT5:
            DebugSerial.println("(keine Aktion)");
            break;

        case InputEvent::BT6:
            DebugSerial.println("(keine Aktion)");
            break;

        default:
            break;
    }
}

// ---------------------------------------------------------
// Deep Sleep
// ---------------------------------------------------------
// Schlafdauer 0 heisst: kein Timer. Der ESP bleibt liegen, bis
// jemand RST zieht - genau das macht der INT-Ausgang des
// Expanders beim naechsten Tastendruck.
//
// Voraussetzung ist, dass INT den Reset als Puls ausloest. Eine
// dauerhaft auf LOW gehaltene RST-Leitung wuerde den ESP im
// Reset festhalten.

void Application::enterDeepSleep()
{
    // Bus dem anderen Master ueberlassen, bevor die Pegel
    // wegfallen
    I2CMasterControl::disable();

    DebugSerial.println("[SYS] Deep Sleep");
    DebugSerial.flush();

    ESP.deepSleep(0, WAKE_RF_MODE);

    // ESP.deepSleep() kehrt kurz zurueck, bevor der Chip
    // tatsaechlich abschaltet.
    delay(100);
}

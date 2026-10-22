#include "application.h"
#include "I2CMasterControl.h"
#include "pinMapping.h"

#include "DebugLogger.h"

#include <ESP8266WiFi.h>

Application::Application()
    : _display(),
      _fs(),
      _framBus(),
      _flashQuotes(_fs),
      _framQuotes(_framBus, _fs),
      _gpioExpander(0x20),
      _inputs(_gpioExpander),
      _wakeupReason(WakeupReason::Reason::UNKNOWN),
      _state(),
      _coldBoot(false),
      _displayReady(false),
      _pulseIdle(HIGH)
{
}

namespace
{
    // Die Zitatliste steht im FRAM (FramQuoteStore). Mit FRAM_INSTALLED = false
    // steht sie in /quotes.txt im LittleFS (QuoteStore). Ist die Liste leer
    // oder nicht lesbar, zeigt die Wand diesen Hinweis statt dunkel zu bleiben.
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

    // Radar (HLK-LD2410S) angeschlossen? Ohne Radar liest GPIO13 wegen des
    // Pull-ups dauerhaft HIGH ("jemand steht davor"). Auf false ignoriert die
    // Firmware INT_HLK: die Wand geht nur mit BT1 an und nach 60 s wieder aus.
    constexpr bool RADAR_INSTALLED = false;

    // FRAM (MB85RC256V auf 0x50) eingebaut? Dann liegt die Zitatliste dort,
    // und eine /quotes.txt im Flash wird einmal ins FRAM uebernommen. Auf false
    // liegt die Liste wie frueher in /quotes.txt im Flash.
    constexpr bool FRAM_INSTALLED = true;
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

    if (!RADAR_INSTALLED)
        DebugSerial.println("[WALL] Radar nicht eingebaut (RADAR_INSTALLED = false), INT_HLK wird ignoriert");

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

    // Tastenstand jetzt sichern: ein Druck waehrend der Warteschleife setzt den ESP zurueck
    PersistentState::save(_state);

    // Was die Wand zeigt, entscheiden die Wand-Regeln
    // (Name bewusst nicht radarHigh: das ist die Methode)
    const bool radarNow = radarHigh();

    // Nach dem Einschalten ist der Inhalt der Module unbekannt (nach
    // einem Firmware-Update steht noch der alte Text): die Wand
    // wird dunkel geschaltet, bevor die Regeln entscheiden.
    if (_coldBoot)
    {
        _display.setPower(false);
        _state.displayState = 0;
        _state.button1Active = 0;
    }

    WallBoot boot;
    boot.displayOn = _state.displayState != 0;
    boot.displayWriting = _state.displayState == 2;
    boot.radarHigh = radarNow;
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
// dann, wenn BT2 tatsaechlich gedrueckt wurde. In jedem
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
// Druck auf BT2 laesst die Anzeige unberuehrt.

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
// displayState = 2 steht samt dem gewaehlten Zitat (Index, Datum)
// im RTC-Speicher, bevor die Module beschrieben werden: bricht
// der Durchlauf dabei ab, schreibt der naechste dieses Zitat neu.

IQuoteStore& Application::quotes()
{
    if (FRAM_INSTALLED)
        return _framQuotes;
    return _flashQuotes;
}

void Application::showQuote(WallAction action)
{
    if (!_fs.begin())
        DebugSerial.println("[WALL] FEHLER: Dateisystem laesst sich nicht einbinden");

    // Zeit nur messen, wenn das FRAM die Liste liefert.
    const uint32_t loadStart = FRAM_INSTALLED ? millis() : 0;
    const QuoteList list = quotes().load();

    if (FRAM_INSTALLED)
    {
        const uint32_t loadMs = millis() - loadStart;
        const FramLoadInfo& info = _framQuotes.lastLoad();
        if (info.busError)
            DebugSerial.println("[QUOTES] FEHLER: FRAM 0x50 nicht lesbar");
        else if (info.damaged)
            DebugSerial.println("[QUOTES] FEHLER: Liste im FRAM beschaedigt (Pruefsumme falsch), nichts gespeichert");
        else if (info.imported)
            DebugSerial.printf("[QUOTES] Liste aus dem Flash ins FRAM uebernommen: %u Bytes in %u ms\n",
                               (unsigned)info.bytes, (unsigned)loadMs);
        else if (info.importFailed)
            DebugSerial.println("[QUOTES] FEHLER: Uebernahme ins FRAM gescheitert (FRAM 0x50 nicht beschreibbar, Kontrolle fehlgeschlagen oder Liste zu lang), Liste aus dem Flash angezeigt, Datei bleibt");
        else
            DebugSerial.printf("[QUOTES] FRAM: %u Bytes in %u ms gelesen\n",
                               (unsigned)info.bytes, (unsigned)loadMs);
    }

    std::string text;
    std::string date;
    std::size_t index = 0;

    if (list.empty())
    {
        DebugSerial.println("[WALL] FEHLER: kein Zitat gespeichert");
        text = NO_TEXT;
    }
    else
    {
        index = selectIndex(list, action, _state.shownIndex,
                            std::string(_state.shownDate));

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

    // Das Ziel wird zusammen mit displayState = 2 gesichert, bevor
    // die Module beschrieben werden: bricht der Durchlauf ab,
    // schreibt der naechste genau dieses Zitat neu. Index und
    // Datum finden den Eintrag auch nach einer verschobenen Liste.
    _state.displayState = 2;
    _state.shownIndex = static_cast<uint8_t>(index);
    memset(_state.shownDate, 0, sizeof(_state.shownDate));
    strncpy(_state.shownDate, date.c_str(), sizeof(_state.shownDate) - 1);

    PersistentState::save(_state);

    ensureDisplayReady();
    _display.show(String(text.c_str()));

    // Erst jetzt einschalten: HT16K33::init() laesst die Anzeige
    // aus, damit kein alter Inhalt aufblitzt
    _display.setPower(true);

    _state.displayState = 1;
    PersistentState::save(_state);
}

// ---------------------------------------------------------
// Radar
// ---------------------------------------------------------
// Einzige Stelle, die INT_HLK liest. Ohne eingebauten Radar
// (RADAR_INSTALLED = false) meldet sie nie "jemand da", sonst
// wuerde der Pull-up die Wand dauerhaft an halten.

bool Application::radarHigh()
{
    return RADAR_INSTALLED && digitalRead(Pins::INT_HLK) == HIGH;
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

        const bool radarNow = radarHigh();

        if (wallShouldTurnOff(radarNow, _state.button1Active != 0, millis()))
        {
            turnWallOff();
            return;
        }
    }
}

void Application::turnWallOff()
{
    // Zustand zuerst sichern: bricht das Abschalten ab, wird die
    // Wand beim naechsten Aufwachen nicht als an behandelt.
    _state.displayState = 0;
    _state.button1Active = 0;

    PersistentState::save(_state);

    _display.setPower(false);

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

#include "application.h"
#include "I2CMasterControl.h"
#include "pinMapping.h"
#include "features.h"
#include "TextLayout.h"
#include "LinkTest.h"

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
      _powerPin(),
      _piPower(_powerPin),
      _port(Serial),
      _link(_port),
      _session(_state.session),
      _linkTestRequested(false)
{
}

namespace
{
    // Die Zitatliste steht im FRAM (FramQuoteStore). Mit Features::FRAM_INSTALLED = false
    // steht sie in /quotes.txt im LittleFS (QuoteStore). Ist die Liste leer
    // oder nicht lesbar, zeigt die Wand diesen Hinweis statt dunkel zu bleiben.
    constexpr char NO_TEXT[] = "KEIN TEXT";

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

    // Nummer der Taste fuer PiSession::onButton und BUTTON|n
    int buttonNumber(InputEvent button)
    {
        switch (button)
        {
            case InputEvent::BT1: return 1;
            case InputEvent::BT2: return 2;
            case InputEvent::BT3: return 3;
            case InputEvent::BT4: return 4;
            case InputEvent::BT5: return 5;
            case InputEvent::BT6: return 6;
            default: return 0;
        }
    }

    // Namen wie in der Spec (Abschnitt 7), nur fuers Log
    const char* stateName(SessionState state)
    {
        switch (state)
        {
            case SessionState::Off: return "AUS";
            case SessionState::Starting: return "EINSCHALTEN";
            case SessionState::Running: return "BETRIEB";
            case SessionState::RadarDebug: return "RADAR-DEBUG";
            case SessionState::ShuttingDown: return "HERUNTERFAHREN";
            case SessionState::Halting: return "HALT-WARTEN";
        }
        return "?";
    }

    // Takt der Sitzung. delay() fuettert dazwischen den Watchdog.
    constexpr unsigned long SESSION_TICK_MS = 20;

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

    // Beim Aufwachen bleibt das Funkteil aus (Features::WAKE_RF_ENABLED = false):
    // es kostet rund 70 mA und etwa 200 ms Bootzeit, die hier niemand braucht.
    constexpr RFMode WAKE_RF_MODE = Features::WAKE_RF_ENABLED ? WAKE_RF_DEFAULT : WAKE_RF_DISABLED;
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
//
// Laeuft eine Sitzung mit dem Pi, folgt danach die Sitzung statt
// der Wand-Regeln, und nach ihrem Ende der Deep Sleep (R10).

void Application::run()
{
    // -----------------------------------------------------
    // 1. Funk
    // -----------------------------------------------------
    // Features::WAKE_RF_ENABLED = false haelt das Funkteil beim Aufwachen schon aus.
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

    // Eine Zeile der Verbindung hat bis 257 Bytes; der Standardpuffer fasst 256.
    Serial.setRxBufferSize(1024);
    DebugSerial.begin(Features::LINK_BAUD);  // same baud as the ESP8266 boot ROM -> boot log readable

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

    // MAGIC und CRC stimmen, die Werte der Sitzung koennen trotzdem
    // unbrauchbar sein (ein Zustand ausserhalb der Liste schliefe nie ein)
    const bool sessionValid = PiSession::valid(_state.session);

    if (!sessionValid)
        PiSession::reset(_state.session);

    _state.wakeCount++;

    // Speisung und Nummern wie vor dem Reset. Nach einem Kaltstart
    // steht hier 0: auch das Flipflop ist dann zurueckgesetzt.
    _piPower.restore(_state.piPowered != 0);

    LinkState numbers;
    numbers.txSeq = _state.txSeq;
    numbers.rxSeq = _state.rxSeq;
    numbers.rxValid = _state.rxValid != 0;
    _link.restore(numbers);

    // -----------------------------------------------------
    // 4. Expander lesen und auswerten
    // -----------------------------------------------------

    I2CMasterControl::begin();

    const uint16_t state = readExpander();

    // Ohne die Schleife entprellt nichts mehr ueber die Zeit -
    // der Reset selbst trennt die Ereignisse, und millis()
    // faengt bei jedem Durchlauf neu an.
    _inputs.setDebounceMs(0);

    // Alle sechs Tasten laufen ueber Toggle-Flipflops (Blatt
    // "Button Debouncing", Spec 4 F9; BT4-BT6 nachgeruestet):
    // jeder Druck kippt den Pegel, und der neue Pegel bleibt
    // stehen, bis der ESP ihn liest. Ein Wechsel ist deshalb
    // genau ein Druck, egal wie kurz er war.
    _inputs.setTrigger(InputEvent::BT1, InputTrigger::ANY_EDGE);
    _inputs.setTrigger(InputEvent::BT2, InputTrigger::ANY_EDGE);
    _inputs.setTrigger(InputEvent::BT3, InputTrigger::ANY_EDGE);
    _inputs.setTrigger(InputEvent::BT4, InputTrigger::ANY_EDGE);
    _inputs.setTrigger(InputEvent::BT5, InputTrigger::ANY_EDGE);
    _inputs.setTrigger(InputEvent::BT6, InputTrigger::ANY_EDGE);

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

    if (!Features::RADAR_INSTALLED)
        DebugSerial.println("[WALL] Radar nicht eingebaut (Features::RADAR_INSTALLED = false), INT_HLK wird ignoriert");

    if (!sessionValid)
        DebugSerial.println("[SESSION] FEHLER: Sitzung im RTC-Speicher ungueltig, zurueckgesetzt");

    // Was resume, startHand und onButton ausloesen, fuehrt
    // executeActions aus, sobald der Tastenstand gesichert ist.
    std::vector<SessionAction> actions;

    // Ein Reset hat die Sitzung unterbrochen: im selben Zustand
    // weiter. Eine abgebrochene eigene Anfrage geht noch einmal
    // raus (R8), die Speisung wird nicht noch einmal geschaltet.
    if (_session.active())
    {
        if (_state.session.state == SessionState::Off)
            DebugSerial.println("[SESSION] Pi aus, PI ANTWORTET NICHT steht noch");
        else
            DebugSerial.printf("[SESSION] weiter in %s\n", stateName(_state.session.state));

        _session.resume(actions);
    }

    // Nach dem Einschalten bleibt die Wand dunkel, bis der
    // Radar oder BT1 sie einschaltet.
    bool button1 = false;

    for (uint8_t i = 0; i < count; i++)
    {
        DebugSerial.printf("[INPUT] %s -> ", buttonName(events[i]));

        if (events[i] == InputEvent::BT1)
            button1 = true;

        handleInput(events[i], actions);
    }

    // Tastenstand jetzt sichern (F3, in jedem Zustand): ein Druck
    // waehrend der Warteschleife setzt den ESP zurueck
    saveState();

    executeActions(actions);

    // -----------------------------------------------------
    // Sitzung mit dem Pi
    // -----------------------------------------------------
    // Anzeige und Leitung gehoeren jetzt der Sitzung: Wand-Regeln,
    // BT1-Minute und Radar entfallen in diesem Durchlauf. Den
    // Verbindungstest gibt es nur ohne Sitzung (handleInput).
    // Nach dem Ende bleibt die Wand dunkel, bis die naechste
    // Radar-Flanke oder BT1 sie einschaltet (R10).

    if (_session.active())
    {
        runSession(actions);

        saveState();

        enterDeepSleep();
        return;
    }

    // Tastenstand ist gesichert: ein Reset im Test wiederholt ihn nicht
    if (_linkTestRequested)
        runLinkTest(_link, 3000);

    // Was die Wand zeigt, entscheiden die Wand-Regeln
    // (Name bewusst nicht radarHigh: das ist die Methode)
    const bool radarNow = radarHigh();

    // Nach dem Einschalten ist der Inhalt der Module unbekannt (nach
    // einem Firmware-Update steht noch der alte Text): die Wand
    // wird dunkel geschaltet, bevor die Regeln entscheiden.
    if (_coldBoot)
    {
        _display.setPower(false);
        _state.displayState = DisplayState::Off;
        _state.button1Active = 0;
    }

    WallBoot boot;
    boot.displayOn = _state.displayState != DisplayState::Off;
    boot.displayWriting = _state.displayState == DisplayState::Writing;
    boot.radarHigh = radarNow;
    boot.button1 = button1;

    const WallAction action = decideOnBoot(boot);

    if (button1)
        _state.button1Active = 1;

    if (action != WallAction::None)
        showQuote(action);

    if (_state.displayState == DisplayState::On)
        runWallLoop();

    // -----------------------------------------------------
    // 6. Zustand sichern und schlafen
    // -----------------------------------------------------

    // Auch die Nummern: der Verbindungstest hat eine verbraucht
    saveState();

    enterDeepSleep();
}

// ---------------------------------------------------------
// Zustand sichern
// ---------------------------------------------------------
// Die Sitzung schreibt direkt in _state.session, die Speisung
// fuehrt executeActions nach. Nur die Nummern der Verbindung
// stehen in PiLink und kommen hier dazu.

void Application::saveState()
{
    const LinkState numbers = _link.state();

    _state.txSeq = numbers.txSeq;
    _state.rxSeq = numbers.rxSeq;
    _state.rxValid = numbers.rxValid ? 1 : 0;

    PersistentState::save(_state);
}

// ---------------------------------------------------------
// Sitzung
// ---------------------------------------------------------
// Die Logik steht in PiSession (lib/core), hier nur der Takt
// und die Verdrahtung. Jeder Takt holt alles ab, was auf der
// Leitung wartet, und beantwortet eine Anfrage des Pi, bevor er
// die naechste Zeile liest. Danach zaehlt onTick die Zeit und
// schickt, was ansteht, und der Zustand wird gesichert.
//
// R14: Der Pi schreibt jetzt auf den Bus. Der ESP gibt ihn hier
// frei und nimmt ihn nur noch fuer seine eigenen Anzeigetexte
// (showSessionText, sessionDisplayOff). Die kommen nur vor, wenn
// der Pi nicht schreibt: beim Einschalten, nach OK auf SHUTDOWN
// und nach einem harten Aus.

void Application::runSession(std::vector<SessionAction>& actions)
{
    I2CMasterControl::disable();

    // millis() zaehlt ab diesem Reset: der erste Takt nimmt die
    // Zeit seit dem Start mit (R1)
    unsigned long lastTick = 0;
    unsigned long discarded = _link.discarded();

    while (_session.active())
    {
        const unsigned long tickStart = millis();
        const SessionState before = _state.session.state;

        // poll meldet ein Ereignis nach dem anderen: bis nichts mehr wartet
        while (true)
        {
            const LinkEvent ev = _link.poll(millis());

            if (ev.kind == LinkEvent::Kind::None)
                break;

            switch (ev.kind)
            {
                case LinkEvent::Kind::Request:
                    DebugSerial.printf("[LINK] Pi #%02X %s%s%s\n", (unsigned)ev.message.seq,
                                       ev.message.command.c_str(),
                                       ev.message.data.empty() ? "" : "|", ev.message.data.c_str());
                    break;
                case LinkEvent::Kind::Response:
                    DebugSerial.printf("[LINK] Antwort %s\n", ev.message.command.c_str());
                    break;
                default:
                    DebugSerial.printf("[LINK] keine Antwort auf %s\n", ev.message.command.c_str());
                    break;
            }

            _session.onLink(ev, actions);

            // Die Antwort (Reply) muss raus, bevor poll weiterliest
            executeActions(actions);
        }

        // PiLink loggt selbst nicht
        if (_link.discarded() > discarded)
        {
            discarded = _link.discarded();
            DebugSerial.printf("[LINK] Zeile verworfen (%lu insgesamt): %s\n",
                               discarded, LinkCodec::errorName(_link.lastError()));
        }

        const unsigned long now = millis();

        _session.onTick(now - lastTick, _link.busy(), actions);
        lastTick = now;

        executeActions(actions);

        if (_state.session.state != before)
            DebugSerial.printf("[SESSION] %s -> %s\n", stateName(before), stateName(_state.session.state));

        // In jedem Takt sichern: die Zeitzaehler aendern sich in
        // jedem Takt. Ein Reset verliert so ausser sich selbst nur
        // die Zeit seit diesem Takt (R1), und auch eine schnelle
        // Folge von Resets laesst die Fristen weiterlaufen. Kostet
        // eine CRC ueber 52 Byte und 15 Woerter RTC-Speicher.
        saveState();

        const unsigned long spent = millis() - tickStart;

        if (spent < SESSION_TICK_MS)
            delay(SESSION_TICK_MS - spent);
        else
            yield();
    }

    DebugSerial.println("[SESSION] zu Ende");
}

// Reihenfolge wie geliefert: PiSession schaltet die Speisung aus,
// bevor sie PI ANTWORTET NICHT zeigt (R14).

void Application::executeActions(std::vector<SessionAction>& actions)
{
    for (const SessionAction& action : actions)
    {
        switch (action.kind)
        {
            case SessionAction::Kind::PowerOn:
            case SessionAction::Kind::PowerOff:
            {
                const bool on = action.kind == SessionAction::Kind::PowerOn;

                // Erst sichern, dann pulsen. Ein Reset mitten im Puls
                // laesst GPIO12 auf den Ruhepegel zurueckfallen und
                // vollendet ihn damit; der gesicherte Stand stimmt dann
                // schon. In der anderen Reihenfolge schaltete die
                // fortgesetzte Sitzung ein zweites Mal.
                _state.piPowered = on ? 1 : 0;
                saveState();

                if (_piPower.switchTo(on))
                    DebugSerial.printf("[PI] Speisung %s\n", on ? "ein" : "aus");
                else
                    DebugSerial.printf("[PI] Speisung war schon %s\n", on ? "ein" : "aus");
                break;
            }

            case SessionAction::Kind::Send:
                // awaiting hat die Sitzung schon gesetzt
                if (_link.send(action.command, action.data, millis()))
                    DebugSerial.printf("[LINK] -> %s%s%s\n", action.command.c_str(),
                                       action.data.empty() ? "" : "|", action.data.c_str());
                else
                    DebugSerial.printf("[LINK] FEHLER: %s nicht gesendet\n", action.command.c_str());
                break;

            case SessionAction::Kind::Reply:
                if (!_link.reply(action.command, action.data))
                    DebugSerial.printf("[LINK] FEHLER: Antwort %s ohne offene Anfrage\n", action.command.c_str());
                break;

            case SessionAction::Kind::Show:
                showSessionText(action.command);
                break;

            case SessionAction::Kind::DisplayOff:
                sessionDisplayOff();
                break;

            case SessionAction::Kind::Log:
                DebugSerial.printf("[SESSION] %s\n", action.command.c_str());
                break;
        }
    }

    actions.clear();
}

// Die Texte werden wie ein Zitat gesetzt (R11). Der Bus ist nur
// fuer diese Zugriffe beim ESP. begin() laeuft hoechstens einmal
// pro Durchlauf.
//
// I2CMasterControl zaehlt nicht mit: Display gibt den Bus nach
// jedem eigenen Zugriff schon frei, die Klammer hier haelt ihn
// nicht ueber alle drei Aufrufe. Das genuegt, weil der Pi in
// diesen Zustaenden nicht schreibt (R14).

void Application::showSessionText(const std::string& text)
{
    DebugSerial.printf("[SESSION] Anzeige \"%s\"\n", text.c_str());

    I2CMasterControl::enable();

    ensureDisplayReady();
    _display.show(String(text.c_str()));
    _display.setPower(true);

    I2CMasterControl::disable();

    _state.displayState = DisplayState::On;
}

// Wie turnWallOff: danach gelten wieder die Wand-Regeln (V1)

void Application::sessionDisplayOff()
{
    DebugSerial.println("[SESSION] Anzeige aus");

    I2CMasterControl::enable();

    ensureDisplayReady();
    _display.setPower(false);

    I2CMasterControl::disable();

    _state.displayState = DisplayState::Off;
    _state.button1Active = 0;
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
// sich nur, wenn tatsaechlich etwas geschrieben wird - eine
// Taste in der Sitzung laesst die Anzeige unberuehrt.

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
// displayState = Writing steht samt dem gewaehlten Zitat (Index, Datum)
// im RTC-Speicher, bevor die Module beschrieben werden: bricht
// der Durchlauf dabei ab, schreibt der naechste dieses Zitat neu.

IQuoteStore& Application::quotes()
{
    if (Features::FRAM_INSTALLED)
        return _framQuotes;
    return _flashQuotes;
}

void Application::showQuote(WallAction action)
{
    if (!_fs.begin())
        DebugSerial.println("[WALL] FEHLER: Dateisystem laesst sich nicht einbinden");

    // Zeit nur messen, wenn das FRAM die Liste liefert.
    const uint32_t loadStart = Features::FRAM_INSTALLED ? millis() : 0;
    const QuoteList list = quotes().load();

    if (Features::FRAM_INSTALLED)
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

    if (!TextLayout::wrap(text).fits)
        DebugSerial.printf("[TEXT] Warnung: passt nicht auf die Anzeige (4 x 24, Umbruch an Wortgrenzen): \"%s\"\n",
                           text.c_str());

    DebugSerial.printf("[WALL] %s -> #%u %s \"%s\"\n",
                       actionName(action),
                       (unsigned)index,
                       date.c_str(),
                       text.c_str());

    // Das Ziel wird zusammen mit displayState = Writing gesichert, bevor
    // die Module beschrieben werden: bricht der Durchlauf ab,
    // schreibt der naechste genau dieses Zitat neu. Index und
    // Datum finden den Eintrag auch nach einer verschobenen Liste.
    _state.displayState = DisplayState::Writing;
    _state.shownIndex = static_cast<uint8_t>(index);
    memset(_state.shownDate, 0, sizeof(_state.shownDate));
    strncpy(_state.shownDate, date.c_str(), sizeof(_state.shownDate) - 1);

    saveState();

    ensureDisplayReady();
    _display.show(String(text.c_str()));

    // Erst jetzt einschalten: HT16K33::init() laesst die Anzeige
    // aus, damit kein alter Inhalt aufblitzt
    _display.setPower(true);

    _state.displayState = DisplayState::On;
    saveState();
}

// ---------------------------------------------------------
// Radar
// ---------------------------------------------------------
// Einzige Stelle, die INT_HLK liest. Ohne eingebauten Radar
// (Features::RADAR_INSTALLED = false) meldet sie nie "jemand da", sonst
// wuerde der Pull-up die Wand dauerhaft an halten.

bool Application::radarHigh()
{
    return Features::RADAR_INSTALLED && digitalRead(Pins::INT_HLK) == HIGH;
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
    _state.displayState = DisplayState::Off;
    _state.button1Active = 0;

    saveState();

    _display.setPower(false);

    DebugSerial.println("[WALL] aus");
}

// ---------------------------------------------------------
// Zuweisung Taster -> Aktion (Tabelle 5.2)
// ---------------------------------------------------------
// Welcher Taster hier ankommt, bestimmt die Trigger-
// Konfiguration in run(); alle sechs stehen auf ANY_EDGE.
//
// In einer Sitzung entscheidet PiSession: BT2 faehrt den Pi
// herunter oder wird gemerkt, die anderen gehen im Betrieb als
// BUTTON|n an den Pi. Ist der Pi aus, gilt die Zuweisung hier:
// BT2 startet eine Sitzung HAND, BT1 wirkt ueber die Wand-
// Regeln, BT3 startet den Verbindungstest. Steht noch
// PI ANTWORTET NICHT (D18), startet nur BT2 etwas.

void Application::handleInput(InputEvent button, std::vector<SessionAction>& actions)
{
    if (_state.session.state != SessionState::Off)
    {
        DebugSerial.println("an die Sitzung");
        _session.onButton(buttonNumber(button), actions);
        return;
    }

    if (_session.active() && button != InputEvent::BT2)
    {
        DebugSerial.println("(keine Aktion, PI ANTWORTET NICHT steht noch)");
        return;
    }

    switch (button)
    {
        case InputEvent::BT1:
            DebugSerial.println("ueber die Wand-Regeln");
            break;

        case InputEvent::BT2:
            DebugSerial.println("Pi ein, Sitzung HAND");
            _session.startHand(actions);
            break;

        case InputEvent::BT3:
            DebugSerial.println("Verbindungstest zum Pi");
            _linkTestRequested = true;
            break;

        case InputEvent::BT4:
        case InputEvent::BT5:
        case InputEvent::BT6:
            DebugSerial.println("(keine Aktion ohne Sitzung)");
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

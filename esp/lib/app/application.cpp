#include "application.h"
#include "I2CMasterControl.h"
#include "pinMapping.h"
#include "features.h"
#include "TextLayout.h"
#include "LinkTest.h"
#include "CivilTime.h"
#include "QuoteCheck.h"
#include "TimeSync.h"

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
      _piPower(_powerPin, Features::PI_MIN_OFF_MS),
      _port(Serial),
      _link(_port),
      _session(_state.session, _state.night),
      _linkTestRequested(false),
      _radioOn(false),
      _syncFailed(false),
      _portalDone(false),
      _fsReady(false),
      _listRead(false),
      _coldListDone(false),
      _nightWaitLogged(false),
      _refusedLogged(false),
      _syncWaitLogged(false),
      _clockMs(0),
      _sessionSinceMs(0)
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

    // Nur fuers Log (R15)
    const char* resultName(NightResult result)
    {
        switch (result)
        {
            case NightResult::None: return "keins";
            case NightResult::Ok: return "Ok";
            case NightResult::NoReady: return "NoReady";
            case NightResult::NoAnswer: return "NoAnswer";
            case NightResult::Error: return "Error";
            case NightResult::Rejected: return "Rejected";
            case NightResult::SessionEnded: return "SessionEnded";
            case NightResult::NoClock: return "NoClock";
            case NightResult::StoreFailed: return "StoreFailed";
        }
        return "?";
    }

    const char* statusName(NightStatus status)
    {
        switch (status)
        {
            case NightStatus::Idle: return "Idle";
            case NightStatus::Wanted: return "Wanted";
            case NightStatus::Got: return "Got";
            case NightStatus::Failed: return "Failed";
        }
        return "?";
    }

    // Text aus dem RTC-Speicher, auch ohne NUL nie ueber das Feld hinaus
    std::string field(const char* text, std::size_t size)
    {
        const void* end = memchr(text, '\0', size);
        return std::string(text, end ? static_cast<std::size_t>(static_cast<const char*>(end) - text) : size);
    }

    // Text ins Feld, gekuerzt und mit NUL
    void setField(char* dest, std::size_t size, const std::string& text)
    {
        memset(dest, 0, size);
        strncpy(dest, text.c_str(), size - 1);
    }

    // Takt der Sitzung. delay() fuettert dazwischen den Watchdog.
    constexpr unsigned long SESSION_TICK_MS = 20;

    // So oft liest die Wand den Radar, solange sie an ist. Das
    // Delay fuettert zugleich den Watchdog.
    constexpr unsigned long WALL_POLL_MS = 200;

    // So oft entscheidet der Weckplan, solange der ESP wach ist
    // (Wand an, Sitzung): Mitternacht kommt dann ohne Timer (Z11)
    constexpr unsigned long PLAN_INTERVAL_MS = 1000;

    // M3-a: WLAN und NTP hoechstens 15 s. TimeSync kann um etwa
    // 50 ms und das Abschalten ueberziehen, darum 14 s.
    constexpr unsigned long SYNC_TIMEOUT_MS = 14000;

    // M3-a: Portal nur nach einem Kaltstart ohne Zugangsdaten
    constexpr unsigned long PORTAL_S = 180;

    // Nur falls ein Auftrag am Ende eines Durchlaufs nicht beginnt
    // (darf nicht vorkommen): spaeter noch einmal entscheiden
    constexpr uint32_t RETRY_SLEEP_S = 600;

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
}

// ---------------------------------------------------------
// Application::run()
// ---------------------------------------------------------
// Ein Durchlauf pro Tastendruck oder Timer. Die Reihenfolge ist
// nicht beliebig:
//
//   1. Funk aus, bevor irgendetwas Strom zieht
//   2. Weckgrund lesen, solange INT noch anliegt
//   3. Zustand und Uhr aus dem RTC-Speicher
//   4. Expander lesen - moeglichst frueh, weil der Taster
//      nur so lange lesbar ist, wie er gedrueckt wird
//   5. erst danach alles, was Zeit kostet: Ausgaben, Anzeige
//
// Laeuft eine Sitzung mit dem Pi, folgt danach die Sitzung statt
// der Wand-Regeln (in der Nacht mit ihnen). Am Ende entscheidet
// der Weckplan: abgleichen, den Auftrag der Nacht beginnen oder
// schlafen bis zum naechsten Termin.

void Application::run()
{
    // -----------------------------------------------------
    // 1. Funk
    // -----------------------------------------------------
    // Ob das Funkteil beim Aufwachen bereit ist, legt jede
    // Schlafstrecke selbst fest (enterDeepSleep). Auch dann bleibt
    // es aus, bis TimeSync es braucht. Beim Kaltstart zieht der ESP
    // die Betriebsart aus dem Flash und faehrt WLAN hoch, deshalb
    // hier explizit abschalten.
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
    // 3. Zustand und Uhr aus dem RTC-Speicher
    // -----------------------------------------------------

    _coldBoot = !PersistentState::load(_state);

    // MAGIC und CRC stimmen, die Werte der Sitzung koennen trotzdem
    // unbrauchbar sein (ein Zustand ausserhalb der Liste schliefe nie ein)
    const bool sessionValid = PiSession::valid(_state.session);

    if (!sessionValid)
        PiSession::reset(_state.session);

    // Ebenso der Auftrag der Nacht (Zaehler, Texte ohne NUL)
    const bool nightValid = NightJob::valid(_state.night);

    if (!nightValid)
        NightJob::reset(_state.night);

    // Nach einem Kaltstart sind Uhr und Auftrag unbekannt. setDefaults
    // hat beides schon geleert; hier steht es ausdruecklich.
    if (_coldBoot)
    {
        Clock::reset(_state.clock);
        NightJob::reset(_state.night);

        // Nach dem Einschalten ist das Funkteil an. Ein Reset vor dem
        // ersten Schlaf (Taste waehrend Abgleich oder Portal) behaelt
        // den Funk so; sonst bliebe die Uhr bis zu 3 h unbekannt.
        _state.clock.radio = 1;
    }

    // N1, R13: die geplante Strecke zaehlt ganz. Vor der Zeit geweckt
    // ist jedes Wecken ausser Timer und Einschalten; die Uhr gilt dann
    // als ungenau, bis der naechste Abgleich sie stellt.
    const bool early = _wakeupReason != WakeupReason::Reason::TIMER &&
                       _wakeupReason != WakeupReason::Reason::POWER_ON;

    Clock::onBoot(_state.clock, early);

    // Funk hat dieser Durchlauf nach einem Kaltstart oder wenn die
    // letzte Schlafstrecke mit Funk geplant war. Abgeglichen wird
    // trotzdem nur, wenn der Weckplan es verlangt (plan).
    _radioOn = _coldBoot || _state.clock.radio != 0;

    // GET laeuft nur in einer Sitzung. Steht Wanted ohne Sitzung (die
    // Sitzung war ungueltig), ist der Versuch gescheitert wie nach goOff.
    const bool staleGet = !_session.active() && _state.night.status == NightStatus::Wanted;

    if (staleGet)
    {
        _state.night.status = NightStatus::Failed;
        if (_state.night.result == NightResult::None)
            _state.night.result = NightResult::SessionEnded;
    }

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

    if (!nightValid)
        DebugSerial.println("[NIGHT] FEHLER: Auftrag der Nacht im RTC-Speicher ungueltig, zurueckgesetzt");

    if (staleGet)
        DebugSerial.println("[NIGHT] Auftrag ohne Sitzung: Versuch gescheitert");

    // N4, R4: bei jedem Wecken, solange der Schalter an ist
    if (Features::NIGHT_TEST)
        DebugSerial.printf("[NIGHT] NIGHT_TEST AN: der erste Abgleich nach dem Kaltstart stellt die Uhr %lu s vor Mitternacht\n",
                           (unsigned long)Features::NIGHT_TEST_LEAD_S);

    logClock(early ? "Start (vor der Zeit geweckt)" : "Start");
    logNight();

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
            DebugSerial.printf("[SESSION] weiter in %s%s\n", stateName(_state.session.state),
                               nightSession() ? " (NACHT)" : "");

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
    // Sitzung oder Wand-Regeln
    // -----------------------------------------------------
    // In einer Sitzung HAND gehoeren Anzeige und Leitung der Sitzung:
    // Wand-Regeln, BT1-Minute und Radar entfallen, die Liste bleibt
    // ungelesen (R6). In einer Sitzung NACHT gelten die Wand-Regeln
    // weiter (N2); der Pi nutzt den Bus in der Nacht nicht. Den
    // Verbindungstest gibt es nur ohne Sitzung (handleInput).

    if (_session.active())
    {
        if (nightSession())
            wallOnBoot(button1);
    }
    else
    {
        // Tastenstand ist gesichert: ein Reset im Test wiederholt ihn nicht
        if (_linkTestRequested)
            runLinkTest(_link, 3000);

        // Nach dem Einschalten ist der Inhalt der Module unbekannt (nach
        // einem Firmware-Update steht noch der alte Text): die Wand
        // wird dunkel geschaltet, bevor die Regeln entscheiden.
        if (_coldBoot)
        {
            _display.setPower(false);
            _state.displayState = DisplayState::Off;
            _state.button1Active = 0;
        }

        // Schritte 3 und 4 vor den Wand-Regeln: BT1 zeigt ein eben
        // nachgetragenes Zitat schon
        catchUpNight();

        wallOnBoot(button1);
    }

    // -----------------------------------------------------
    // 6. Wach bleiben, entscheiden, schlafen
    // -----------------------------------------------------
    // Sitzung und Wand halten den ESP wach; beide fragen jede Sekunde
    // den Weckplan. Danach entscheidet er ein letztes Mal: StartNight
    // beginnt den Auftrag und fuehrt zurueck in die Sitzung, Sleep
    // beendet den Durchlauf.

    while (true)
    {
        if (_session.active())
        {
            runSession(actions);

            saveState();

            // Schritt 9: der Pi ist aus, das Zitat kommt in die Liste
            catchUpNight();
            continue;
        }

        // Wand an: Radar, BT1, oder noch nach einer Sitzung NACHT
        if (_state.displayState == DisplayState::On)
        {
            runWallLoop(actions);
            continue;
        }

        WakeDecision decision = plan();

        if (decision.kind == WakeKind::StartNight)
        {
            if (beginNightAttempt(actions) != NightStart::Ignored)
                continue;

            DebugSerial.printf("[NIGHT] FEHLER: Auftrag nicht begonnen, neu entscheiden in %lu s\n",
                               (unsigned long)RETRY_SLEEP_S);

            decision = WakeDecision{WakeKind::Sleep, RETRY_SLEEP_S, false};
        }

        // R14, R15: ohne Uhr laesst der ESP die Nacht aus
        if (!_state.clock.valid)
            _state.night.result = NightResult::NoClock;

        enterDeepSleep(decision.sleepS, decision.radio);
        return;
    }
}

// ---------------------------------------------------------
// Zustand sichern
// ---------------------------------------------------------
// Die Sitzung schreibt direkt in _state.session und _state.night,
// die Speisung fuehrt executeActions nach. Die Uhr zaehlt hier die
// wach verbrachte Zeit dazu: ein Reset verliert nur die Zeit seit
// dem letzten Sichern. Die Nummern der Verbindung stehen in PiLink
// und kommen hier dazu.

void Application::saveState()
{
    advanceClock();

    const LinkState numbers = _link.state();

    _state.txSeq = numbers.txSeq;
    _state.rxSeq = numbers.rxSeq;
    _state.rxValid = numbers.rxValid ? 1 : 0;

    PersistentState::save(_state);
}

void Application::advanceClock()
{
    const unsigned long now = millis();

    Clock::advance(_state.clock, now - _clockMs);
    _clockMs = now;
}

// ---------------------------------------------------------
// Sitzung
// ---------------------------------------------------------
// Die Logik steht in PiSession (lib/core), hier nur der Takt
// und die Verdrahtung. Jeder Takt holt alles ab, was auf der
// Leitung wartet, und beantwortet eine Anfrage des Pi, bevor er
// die naechste Zeile liest. Danach zaehlt onTick die Zeit und
// schickt, was ansteht.
//
// Gesichert wird, bevor die Aktionen laufen: nach onLink und nach
// onTick. Ein neuer Zustand (BETRIEB nach READY, RADAR-DEBUG,
// HERUNTERFAHREN, HALT-WARTEN) steht so im RTC-Speicher, bevor
// die Antwort an den Pi geht und bevor ein langsames Show die CPU
// fuer 0,3-0,5 s festhaelt. Ein Reset faellt danach in den neuen
// Zustand zurueck. Was dabei noch einmal geschieht, schadet nicht:
// jede Anfrage des Pi darf zweimal beantwortet werden, SESSION und
// SHUTDOWN gehen mit neuer Nummer noch einmal raus (R8).
//
// R14: Der Pi schreibt jetzt auf den Bus. Der ESP gibt ihn hier
// frei und nimmt ihn nur noch fuer seine eigenen Anzeigetexte
// (showSessionText, sessionDisplayOff). Die kommen nur vor, wenn
// der Pi nicht schreibt: beim Einschalten, nach OK auf SHUTDOWN
// und nach einem harten Aus. In einer Sitzung NACHT nutzt der Pi
// den Bus nicht; dort schreibt der ESP auch Zitate (N2, Z11).
//
// Jede Sekunde fragt der Takt den Weckplan (plan). Ein Abgleich
// haelt die Sitzung dabei bis 15 s an (R3); die Fristen zaehlen
// die Zeit danach mit.

void Application::runSession(std::vector<SessionAction>& actions)
{
    I2CMasterControl::disable();

    // millis() zaehlt ab diesem Reset: der erste Takt nimmt die
    // Zeit seit dem Start mit (R1). Eine Sitzung, die erst spaeter
    // in diesem Durchlauf begann (Nacht), zaehlt ab ihrem Beginn.
    unsigned long lastTick = _sessionSinceMs;
    unsigned long lastWall = millis();
    unsigned long lastPlan = millis();
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

            // Erst sichern, dann antworten (M-1, I-1)
            saveState();

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

        // In jedem Takt sichern, auch ohne neuen Zustand: die
        // Zeitzaehler aendern sich in jedem Takt. Ein Reset verliert
        // so ausser sich selbst nur die Zeit seit diesem Takt (R1),
        // und auch eine schnelle Folge von Resets laesst die Fristen
        // weiterlaufen. Jede Sicherung kostet eine CRC ueber 300 Byte
        // und 77 Woerter RTC-Speicher.
        saveState();

        executeActions(actions);

        if (_state.session.state != before)
            DebugSerial.printf("[SESSION] %s -> %s\n", stateName(before), stateName(_state.session.state));

        // Am Ende des Takts noch einmal: Show und DisplayOff
        // aendern displayState
        saveState();

        // N2: in der Nacht gelten die Wand-Regeln weiter, im selben
        // Abstand wie in runWallLoop. Einschalten kommt ueber den
        // Reset (wallOnBoot), hier nur das Ausschalten.
        if (nightSession() && _state.displayState == DisplayState::On &&
            millis() - lastWall >= WALL_POLL_MS)
        {
            lastWall = millis();

            if (wallShouldTurnOff(radarHigh(), _state.button1Active != 0, millis()))
                turnWallOff();
        }

        // Schritt 5: Sleep heisst hier "weiter". StartNight holt das
        // Zitat in dieser Sitzung (M4-a), auch von Hand.
        if (millis() - lastPlan >= PLAN_INTERVAL_MS)
        {
            lastPlan = millis();

            if (plan().kind == WakeKind::StartNight)
            {
                const unsigned long since = _sessionSinceMs;

                beginNightAttempt(actions);

                // Hier eben begonnen (die alte Sitzung ging gerade aus):
                // die Fristen zaehlen ab ihrem Beginn, nach der Pi-Pause
                if (_sessionSinceMs != since)
                    lastTick = _sessionSinceMs;
            }
        }

        const unsigned long spent = millis() - tickStart;

        if (spent < SESSION_TICK_MS)
            delay(SESSION_TICK_MS - spent);
        else
            yield();
    }

    DebugSerial.println("[SESSION] zu Ende");
    logNight();
}

// Reihenfolge wie geliefert: PiSession schaltet die Speisung aus,
// bevor sie PI ANTWORTET NICHT zeigt (R14).

void Application::executeActions(std::vector<SessionAction>& actions)
{
    // Was die Sitzung auf ein nicht gesendetes Send hin ausloest
    std::vector<SessionAction> followUp;

    for (const SessionAction& action : actions)
    {
        switch (action.kind)
        {
            case SessionAction::Kind::PowerOn:
            case SessionAction::Kind::PowerOff:
            {
                const bool on = action.kind == SessionAction::Kind::PowerOn;

                // Pi-Pause, falls der ESP den Pi eben erst ausgeschaltet
                // hat. Vor dem Sichern: ein Reset in der Pause hinterlaesst
                // so keinen Pi, der als ein gilt und noch aus ist.
                if (on)
                {
                    const unsigned long waited = _piPower.waitMinOff();

                    if (waited > 0)
                        DebugSerial.printf("[PI] %lu ms Pause vor dem Einschalten (mindestens %lu ms aus)\n",
                                           waited, Features::PI_MIN_OFF_MS);
                }

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
                {
                    DebugSerial.printf("[LINK] -> %s%s%s\n", action.command.c_str(),
                                       action.data.empty() ? "" : "|", action.data.c_str());

                    // Die Nummer ist verbraucht: gleich sichern. Sonst ginge
                    // nach einem Reset die naechste Anfrage mit derselben
                    // Nummer raus, und der Pi hielte sie fuer eine
                    // Wiederholung (M-1).
                    saveState();
                }
                else
                {
                    DebugSerial.printf("[LINK] FEHLER: %s nicht gesendet\n", action.command.c_str());

                    // Ohne Send kommt weder Antwort noch Frist, und awaiting
                    // bliebe stehen. Die Sitzung bekommt die Frist gleich (M-2).
                    LinkEvent expired;
                    expired.kind = LinkEvent::Kind::Expired;
                    expired.message.command = action.command;
                    expired.message.data = action.data;
                    _session.onLink(expired, followUp);
                }
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

            case SessionAction::Kind::QuoteReady:
                DebugSerial.printf("[NIGHT] Zitat der Nacht %s: \"%s\"\n", _state.night.date,
                                   action.command.c_str());

                // Z11, N2: leuchtet die Wand in der Nacht, steht das neue
                // Zitat sofort da, aus dem RTC-Speicher; die Position steht
                // dann beim neuesten. Von Hand gehoert die Anzeige dem Pi.
                if (nightSession() && _state.displayState == DisplayState::On)
                    writeQuote(field(_state.night.quote, sizeof(_state.night.quote)), 0,
                               field(_state.night.date, sizeof(_state.night.date)));
                break;
        }
    }

    actions.clear();

    // Wie nach onLink: erst sichern, dann ausfuehren. Eine Frist
    // loest nie ein Send aus (das kommt nur aus onTick), die
    // Rekursion endet also hier.
    if (!followUp.empty())
    {
        saveState();
        executeActions(followUp);
    }
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

IQuoteStore& Application::quotes()
{
    if (Features::FRAM_INSTALLED)
        return _framQuotes;
    return _flashQuotes;
}

// ---------------------------------------------------------
// Zitatliste
// ---------------------------------------------------------
// Das Dateisystem wird erst beim ersten Lesen eingebunden, also nur
// in Durchlaeufen, die die Liste tatsaechlich brauchen (Briefkasten,
// Flash-Speicher).
//
// R6: Der neueste Text der Liste ist der Vortag des naechsten GET.
// Jedes Lesen erneuert ihn im RTC-Speicher, aber nur mit einem Text,
// den auch die Pruefung des Zitats annimmt (die Leitung nimmt nur
// Zeichen 0x20-0x7E). Sonst bleibt er leer: eine neue Kette.

QuoteList Application::loadQuotes()
{
    if (!_fsReady)
    {
        _fsReady = _fs.begin();

        if (!_fsReady)
            DebugSerial.println("[QUOTES] FEHLER: Dateisystem laesst sich nicht einbinden");
    }

    // Zeit nur messen, wenn das FRAM die Liste liefert.
    const uint32_t loadStart = Features::FRAM_INSTALLED ? millis() : 0;
    const QuoteList list = quotes().load();
    bool readable = true;

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

        readable = !info.busError && !info.damaged;
    }

    if (readable)
    {
        std::string newest;

        if (!list.empty() && QuoteCheck::acceptable(list.at(0).text))
            newest = list.at(0).text;

        setField(_state.night.yesterday, sizeof(_state.night.yesterday), newest);
        _listRead = true;
    }

    return list;
}

// Das Zitat bleibt stehen, bis etwas anderes geschrieben wird -
// die HT16K33 halten ihren Inhalt selbst, auch ueber einen
// Reset des ESP hinweg.

void Application::showQuote(WallAction action)
{
    const QuoteList list = loadQuotes();

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

    writeQuote(text, index, date);
}

// Das Ziel wird zusammen mit displayState = Writing gesichert, bevor
// die Module beschrieben werden: bricht der Durchlauf ab, schreibt
// der naechste genau dieses Zitat neu. Index und Datum finden den
// Eintrag auch nach einer verschobenen Liste.

void Application::writeQuote(const std::string& text, std::size_t index, const std::string& date)
{
    _state.displayState = DisplayState::Writing;
    _state.shownIndex = static_cast<uint8_t>(index);
    setField(_state.shownDate, sizeof(_state.shownDate), date);

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
// Wand-Regeln beim Start
// ---------------------------------------------------------
// Was die Wand zeigt, entscheiden die Wand-Regeln. Ohne Sitzung
// und in einer Sitzung NACHT (N2).

void Application::wallOnBoot(bool button1)
{
    WallBoot boot;
    boot.displayOn = _state.displayState != DisplayState::Off;
    boot.displayWriting = _state.displayState == DisplayState::Writing;
    boot.radarHigh = radarHigh();
    boot.button1 = button1;

    const WallAction action = decideOnBoot(boot);

    if (button1)
        _state.button1Active = 1;

    if (action != WallAction::None)
        showQuote(action);
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
//
// Z11: Wach gibt es kein Timer-Wecken. Der ESP fragt deshalb jede
// Sekunde den Weckplan; um Mitternacht beginnt er den Auftrag, und
// die Wand-Regeln laufen in der Sitzung NACHT weiter.

void Application::runWallLoop(std::vector<SessionAction>& actions)
{
    unsigned long lastPlan = millis();

    while (true)
    {
        delay(WALL_POLL_MS);

        if (wallShouldTurnOff(radarHigh(), _state.button1Active != 0, millis()))
        {
            turnWallOff();
            return;
        }

        if (millis() - lastPlan >= PLAN_INTERVAL_MS)
        {
            lastPlan = millis();

            if (plan().kind == WakeKind::StartNight &&
                beginNightAttempt(actions) == NightStart::Started)
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
//
// In einer Sitzung NACHT (N2, N3) wirkt BT1 ueber die Wand-Regeln,
// BT2 macht eine Sitzung von Hand daraus, BT3-BT6 tun nichts.

void Application::handleInput(InputEvent button, std::vector<SessionAction>& actions)
{
    if (nightSession())
    {
        switch (button)
        {
            case InputEvent::BT1:
                DebugSerial.println("ueber die Wand-Regeln (Sitzung NACHT)");
                break;

            case InputEvent::BT2:
                DebugSerial.println("an die Sitzung NACHT");
                _session.onButton(buttonNumber(button), actions);
                break;

            default:
                DebugSerial.println("(keine Aktion in der Sitzung NACHT)");
                break;
        }
        return;
    }

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
// Weckplan
// ---------------------------------------------------------
// Die Regeln stehen in WakePlan (lib/core). Vor jeder Entscheidung
// wird die Uhr nachgefuehrt und gesichert. Abgeglichen wird nur auf
// SyncNow, nicht bei jedem Start mit Funk: ein Tastendruck kurz vor
// Mitternacht wartet so nicht auf das WLAN. Nach dem Abgleich
// entscheidet der Plan sofort neu; ein gescheiterter Abgleich gilt
// fuer den Rest des Durchlaufs (R16), es gibt also hoechstens einen
// Abgleich pro Entscheidung.

WakeDecision Application::plan()
{
    while (true)
    {
        saveState();

        const WakeDecision decision = WakePlan::decide(_state.clock, _state.night,
                                                       _radioOn, _syncFailed);

        const bool wantsSync = decision.kind == WakeKind::SyncNow ||
                               decision.kind == WakeKind::RestartWithRadio;

        if (wantsSync && syncWaitsForSession())
        {
            if (!_syncWaitLogged)
            {
                _syncWaitLogged = true;
                DebugSerial.println("[CLOCK] Abgleich wartet: in dieser Sitzung kann jetzt kein Versuch beginnen");
            }
            return decision;
        }

        if (decision.kind == WakeKind::SyncNow)
        {
            syncClock();
            continue;
        }

        if (decision.kind == WakeKind::RestartWithRadio)
            restartWithRadio();

        return decision;
    }
}

// Ein Abgleich haelt die Sitzung bis 15 s an. Nur wenn danach ein
// Versuch beginnen kann: Uhr bekannt, ein neuer Versuch erlaubt,
// kein Zitat, das erst nach der Sitzung in die Liste kann, und die
// Sitzung nimmt den Auftrag an. Geprueft wird wie in
// beginNightAttempt nach markAttempt, das in einer neuen Nacht den
// Status zuruecksetzt; der Auftrag bleibt danach unveraendert.
// RestartWithRadio dient nur dem Abgleich und wartet ebenso.

bool Application::syncWaitsForSession()
{
    if (!_session.active())
        return false;

    NightData& night = _state.night;

    if (!_state.clock.valid || !WakePlan::mayStartAttempt(night, _state.clock))
        return true;

    if (night.pendingWrite && !listAllowed())
        return true;

    const NightData before = night;

    WakePlan::markAttempt(night, _state.clock);

    const bool takes = _session.canRequestQuote();

    night = before;
    return !takes;
}

// M3-a: WLAN nur zum Abgleich, hoechstens 15 s. Das Portal gibt es
// nur nach einem Kaltstart ohne Zugangsdaten, einmal pro Durchlauf.

void Application::syncClock()
{
    if (_coldBoot && !_portalDone && !TimeSync::hasCredentials())
    {
        _portalDone = true;

        DebugSerial.printf("[CLOCK] keine Zugangsdaten: Portal \"ReflectionWall\" fuer %lu s\n",
                           (unsigned long)PORTAL_S);

        TimeSync::portal(PORTAL_S);
    }

    uint32_t ntpUtc = 0;

    if (!TimeSync::hasCredentials())
    {
        _syncFailed = true;
        DebugSerial.println("[CLOCK] kein Abgleich: keine Zugangsdaten");
        return;
    }

    if (!TimeSync::sync(SYNC_TIMEOUT_MS, ntpUtc))
    {
        _syncFailed = true;
        DebugSerial.println("[CLOCK] Abgleich gescheitert, weiter nach eigener Uhr");
        return;
    }

    // Die eigene Uhr erst um die Dauer des Abgleichs nachfuehren,
    // sonst wiche sie im Log um diese Zeit zu wenig ab
    advanceClock();

    const bool wasValid = _state.clock.valid != 0;
    const uint32_t own = _state.clock.utc;

    // R4: der erste Abgleich nach dem Kaltstart legt die Verschiebung
    // fest, jeder spaetere nimmt dieselbe (Clock::synced)
    if (Features::NIGHT_TEST && !wasValid)
        _state.clock.testOffsetS = WakePlan::testOffset(ntpUtc, Features::NIGHT_TEST_LEAD_S);

    Clock::synced(_state.clock, ntpUtc);

    // Die Zeit des Abgleichs steckt schon in ntpUtc
    _clockMs = millis();

    // N1: die eigene Uhr geht hoechstens vor (positiv), bis auf die
    // Ungenauigkeit des RTC-Zaehlers im Deep Sleep
    if (wasValid)
        DebugSerial.printf("[CLOCK] eigene Uhr wich %ld s ab (positiv: ging vor)\n",
                           (long)(static_cast<int64_t>(own) - static_cast<int64_t>(_state.clock.utc)));

    if (Features::NIGHT_TEST && !wasValid)
        DebugSerial.printf("[NIGHT] NIGHT_TEST: Uhr um %ld s verschoben\n", (long)_state.clock.testOffsetS);

    logClock("Abgleich");

    saveState();
}

// ---------------------------------------------------------
// Auftrag der Nacht
// ---------------------------------------------------------
// StartNight kommt jede Sekunde, solange der Termin erreicht ist und
// das Zitat fehlt; decide beachtet den Status nicht. Ein neuer
// Versuch beginnt deshalb nur in einer neuen Nacht oder nach Idle
// und Failed (mayStartAttempt), und er zaehlt nur, wenn die Sitzung
// den Auftrag annimmt (M4-a): markAttempt wird sonst zurueckgenommen.
//
// Ohne Sitzung schaltet der ESP den Pi ein (NACHT); in einer
// laufenden Sitzung holt er das Zitat darin. Ein Zitat der letzten
// Nacht, das noch nicht in der Liste steht, ginge mit dem neuen
// verloren: Es kommt zuerst in die Liste; gelingt das nicht, faellt
// der Versuch aus (StoreFailed), der Termin ist verbraucht.

Application::NightStart Application::beginNightAttempt(std::vector<SessionAction>& actions)
{
    NightData& night = _state.night;

    if (!WakePlan::mayStartAttempt(night, _state.clock))
        return NightStart::Ignored;

    if (night.pendingWrite)
    {
        // In einer Sitzung HAND bleibt die Liste zu (R6): nach der Sitzung
        if (!listAllowed())
        {
            if (!_nightWaitLogged)
            {
                _nightWaitLogged = true;
                DebugSerial.println("[NIGHT] Auftrag wartet bis nach der Sitzung: das Zitat der letzten Nacht fehlt noch in der Liste");
            }
            return NightStart::Ignored;
        }

        if (!writePendingQuote())
        {
            WakePlan::markAttempt(night, _state.clock);
            night.status = NightStatus::Failed;
            night.result = NightResult::StoreFailed;

            DebugSerial.printf("[NIGHT] Versuch %u der Nacht %s ausgelassen: das Zitat der letzten Nacht ist nicht gespeichert\n",
                               (unsigned)night.attempts, night.date);

            saveState();
            return NightStart::Skipped;
        }
    }

    const NightData before = night;

    WakePlan::markAttempt(night, _state.clock);

    const bool newSession = !_session.active();

    if (newSession)
        _session.startNight(actions);

    // RADAR-DEBUG, HERUNTERFAHREN, HALT-WARTEN, PI ANTWORTET NICHT:
    // kein Auftrag, und der Termin bleibt
    if (!_session.requestQuote())
    {
        night = before;

        if (!_refusedLogged)
        {
            _refusedLogged = true;
            DebugSerial.printf("[NIGHT] Auftrag wartet: die Sitzung nimmt in %s keinen an\n",
                               stateName(_state.session.state));
        }
        return NightStart::Ignored;
    }

    // Ohne Sitzung ist der Pi noch aus (PowerOn folgt unten); in einer
    // Sitzung NACHT nutzt er den Bus nicht. Von Hand gilt der Vortag
    // aus dem RTC-Speicher.
    if (listAllowed() && !_listRead)
        loadQuotes();

    DebugSerial.printf("[NIGHT] Versuch %u der Nacht %s %s, Vortag \"%s\"\n",
                       (unsigned)night.attempts, night.date,
                       newSession ? "mit Pi ein (NACHT)" : "in der laufenden Sitzung",
                       night.yesterday);

    // Erst sichern, dann einschalten
    saveState();

    executeActions(actions);

    // Die Fristen der neuen Sitzung zaehlen ab jetzt, nach der Pi-Pause
    if (newSession)
        _sessionSinceMs = millis();

    return NightStart::Started;
}

// Schritte 3 und 4 (R6, R7). Nur ohne Sitzung: der Pi ist aus.

void Application::catchUpNight()
{
    if (_session.active())
        return;

    // Kaltstart in der Nacht (Review Focus 3): die Liste zeigt, ob das
    // Zitat dieser Nacht schon da ist. Das Datum des neuesten Eintrags
    // folgt derselben Regel wie night.date (Nacht 07-01 auf 07-02 =
    // "2026-07-02").
    if (_coldBoot && !_coldListDone)
    {
        _coldListDone = true;

        const QuoteList list = loadQuotes();

        if (_listRead && !list.empty())
            setField(_state.night.doneDate, sizeof(_state.night.doneDate), list.at(0).date);

        DebugSerial.printf("[NIGHT] Kaltstart: neuester Eintrag \"%s\", Vortag \"%s\"\n",
                           _state.night.doneDate, _state.night.yesterday);

        saveState();
    }

    if (_state.night.pendingWrite)
        writePendingQuote();
}

// P1-a: das Zitat der Nacht vorne in die Liste, das aelteste faellt
// nach 30 weg. Scheitert das, bleibt es im RTC-Speicher (R7), und
// jedes spaetere Wecken ohne Sitzung versucht es wieder.
//
// Das Datum ist doneDate: onQuote setzt es aus date, und anders als
// date rueckt es mit einem ausgelassenen Versuch nicht weiter.

bool Application::writePendingQuote()
{
    NightData& night = _state.night;

    const std::string date = field(night.doneDate, sizeof(night.doneDate));
    const std::string quote = field(night.quote, sizeof(night.quote));

    QuoteList list = loadQuotes();

    // Ein Reset nach dem Speichern, bevor pendingWrite = 0 gesichert
    // war: das Zitat steht schon vorne und kommt nicht zweimal hinein
    const bool there = !list.empty() && list.at(0).date == date && list.at(0).text == quote;

    if (!there)
    {
        list.addNewest(date, quote);

        if (!quotes().save(list))
        {
            night.result = NightResult::StoreFailed;

            DebugSerial.printf("[NIGHT] FEHLER: Zitat %s nicht in der Liste gespeichert, bleibt im RTC-Speicher\n",
                               date.c_str());

            saveState();
            return false;
        }
    }

    night.pendingWrite = 0;
    setField(night.yesterday, sizeof(night.yesterday), quote);

    // Ein frueheres StoreFailed ist damit behoben: das Zitat steht
    // in der Liste wie nach einer gewoehnlichen Nacht
    if (night.result == NightResult::StoreFailed)
        night.result = NightResult::Ok;

    DebugSerial.printf("[NIGHT] Zitat %s vorne in der Liste%s\n", date.c_str(),
                       there ? " (stand schon dort)" : "");

    saveState();
    return true;
}

bool Application::listAllowed() const
{
    return !_session.active() || nightSession();
}

bool Application::nightSession() const
{
    return _state.session.state != SessionState::Off &&
           _state.session.reason == StartReason::Night;
}

// ---------------------------------------------------------
// Log von Uhr und Nacht
// ---------------------------------------------------------

void Application::logClock(const char* what)
{
    const ClockData& c = _state.clock;

    if (!c.valid)
    {
        DebugSerial.printf("[CLOCK] %s: unbekannt (kein Abgleich seit dem Kaltstart), Funk %s\n",
                           what, _radioOn ? "an" : "aus");
        return;
    }

    const CivilTime::Local t = CivilTime::toZurich(c.utc);

    DebugSerial.printf("[CLOCK] %s: %04d-%02d-%02d %02d:%02d:%02d %s, %s, Abgleich vor %lu s, Funk %s\n",
                       what, t.year, t.month, t.day, t.hour, t.minute, t.second,
                       t.summer ? "MESZ" : "MEZ",
                       c.exact ? "genau" : "ungenau",
                       (unsigned long)(c.utc - c.lastSyncUtc),
                       _radioOn ? "an" : "aus");
}

// R15: das Ergebnis der Nacht bei jedem Wecken

void Application::logNight()
{
    const NightData& n = _state.night;

    DebugSerial.printf("[NIGHT] Ergebnis %s; Nacht %s, %u Versuch(e), %s; Zitat da fuer %s%s\n",
                       resultName(n.result),
                       n.date[0] ? n.date : "-",
                       (unsigned)n.attempts,
                       statusName(n.status),
                       n.doneDate[0] ? n.doneDate : "-",
                       n.pendingWrite ? ", noch nicht in der Liste" : "");
}

// ---------------------------------------------------------
// Deep Sleep
// ---------------------------------------------------------
// Jede Strecke hat einen Timer: GPIO16 weckt ueber RST (F3),
// spaetestens nach 3 h oder zum naechsten Termin. Davor weckt jeder
// Tastendruck ueber den INT-Ausgang des Expanders; die Uhr zaehlt
// die geplante Strecke dann trotzdem ganz (N1).
//
// Ob das Funkteil beim naechsten Start bereit ist, legt die Strecke
// fest: nur die Strecke, die um Mitternacht endet, und die Strecken
// ohne Uhr brauchen es (WAKE_RF_DEFAULT). Sonst bleibt es aus und
// spart rund 70 mA und 200 ms Bootzeit (WAKE_RF_DISABLED).

void Application::restartWithRadio()
{
    // R3: der Abgleich braucht den Funk, dieser Durchlauf hat ihn
    // nicht. Die Anzeige behaelt ihren Inhalt, eine Sitzung macht
    // nach dem Start weiter wie nach jedem Reset.
    Clock::beforeSleep(_state.clock, 0, true);
    saveState();

    I2CMasterControl::disable();

    DebugSerial.println("[SYS] Neustart mit Funk fuer den Abgleich");
    DebugSerial.flush();

    ESP.deepSleep(1000, WAKE_RF_DEFAULT);

    // ESP.deepSleep() kehrt kurz zurueck, bevor der Chip
    // tatsaechlich abschaltet. Bleibt er wach, startet er neu.
    delay(100);
    ESP.restart();
}

void Application::enterDeepSleep(uint32_t sleepS, bool radio)
{
    // Laenger zaehlt der RTC-Zaehler nicht; die Uhr zaehlt nur, was
    // wirklich geplant ist
    const uint64_t maxS = ESP.deepSleepMax() / 1000000ULL;

    if (sleepS > maxS)
        sleepS = static_cast<uint32_t>(maxS);

    Clock::beforeSleep(_state.clock, sleepS, radio);
    saveState();

    // Bus dem anderen Master ueberlassen, bevor die Pegel
    // wegfallen
    I2CMasterControl::disable();

    DebugSerial.printf("[SYS] Deep Sleep %lu s, Funk beim naechsten Start %s\n",
                       (unsigned long)sleepS, radio ? "an" : "aus");
    DebugSerial.flush();

    ESP.deepSleep(static_cast<uint64_t>(sleepS) * 1000000ULL, radio ? WAKE_RF_DEFAULT : WAKE_RF_DISABLED);

    // ESP.deepSleep() kehrt kurz zurueck, bevor der Chip
    // tatsaechlich abschaltet.
    delay(100);
}

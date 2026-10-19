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
    // Texte fuer das Display, je max. 96 Zeichen.
    // Das Grid bricht an Wortgrenzen um, die Saetze stehen
    // deshalb normal da. Umlaute sind umschrieben - die
    // Segmentanzeige kann sie nicht darstellen.

    constexpr char TEXT_01[] = "Das Leben wird vorwaerts gelebt, aber rueckwaerts verstanden.";
    constexpr char TEXT_02[] = "Wer nach innen schaut, erwacht. Wer nach aussen schaut, traeumt.";
    constexpr char TEXT_03[] = "Nicht weil es schwer ist, wagen wir es nicht. Weil wir nicht wagen, ist es schwer.";
    constexpr char TEXT_04[] = "Zwischen Reiz und Reaktion liegt ein Raum. In diesem Raum liegt deine Freiheit.";
    constexpr char TEXT_05[] = "Man sieht nur mit dem Herzen gut. Das Wesentliche ist fuer die Augen unsichtbar.";
    constexpr char TEXT_06[] = "Glueck ist kein Ort, an dem man ankommt, sondern eine Art zu reisen.";
    constexpr char TEXT_07[] = "Wir haben nicht zu wenig Zeit. Wir haben nur zu viel davon nicht gelebt.";
    constexpr char TEXT_08[] = "Der Fluss, in den du heute steigst, ist morgen ein anderer. Und du auch.";
    constexpr char TEXT_09[] = "Wer ein Warum zum Leben hat, ertraegt fast jedes Wie.";
    constexpr char TEXT_10[] = "Die Stille zwischen den Toenen macht die Musik.";
    constexpr char TEXT_11[] = "Du bist nicht der Sturm. Du bist der Himmel, durch den er zieht.";
    constexpr char TEXT_12[] = "Vielleicht ist der Sinn nicht zu finden, sondern zu geben.";

    constexpr const char* REFLECTION_TEXTS[] =
    {
        TEXT_01, TEXT_02, TEXT_03, TEXT_04,
        TEXT_05, TEXT_06, TEXT_07, TEXT_08,
        TEXT_09, TEXT_10, TEXT_11, TEXT_12
    };

    constexpr uint8_t TEXT_COUNT = sizeof(REFLECTION_TEXTS) / sizeof(REFLECTION_TEXTS[0]);

    // Laengen beim Kompilieren pruefen, damit ein zu langer
    // Satz den Build bricht statt still abgeschnitten zu werden
    constexpr size_t textLength(const char* text)
    {
        return *text ? 1 + textLength(text + 1) : 0;
    }

    constexpr bool allTextsFit(uint8_t index)
    {
        return index == 0
            || (textLength(REFLECTION_TEXTS[index - 1]) <= 96 && allTextsFit(index - 1));
    }

    static_assert(allTextsFit(TEXT_COUNT), "Ein Text ist laenger als 96 Zeichen");

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

    // Die Taster sind aktiv LOW: FALLING_EDGE ist das
    // Druecken, RISING_EDGE das Loslassen, LEVEL_LOW gilt
    // solange gehalten wird.
    _inputs.setTrigger(InputEvent::BT1, InputTrigger::NONE);
    _inputs.setTrigger(InputEvent::BT2, InputTrigger::NONE);
    _inputs.setTrigger(InputEvent::BT3, InputTrigger::NONE);
    _inputs.setTrigger(InputEvent::BT4, InputTrigger::NONE);
    _inputs.setTrigger(InputEvent::BT5, InputTrigger::FALLING_EDGE);
    _inputs.setTrigger(InputEvent::BT6, InputTrigger::FALLING_EDGE);

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

    // Nach dem Einschalten ist die Anzeige leer und die
    // HT16K33 sind unkonfiguriert - hier muss ein Text stehen.
    // Nach einem Reset behalten sie ihren Inhalt, die Anzeige
    // bleibt dann unberuehrt.
    if (_coldBoot)
    {
        DebugSerial.print("[DISPLAY] ");
        showNextText();
    }

    for (uint8_t i = 0; i < count; i++)
    {
        DebugSerial.printf("[INPUT] %s -> ", buttonName(events[i]));

        handleInput(events[i]);
    }

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

// Der Text bleibt stehen, bis etwas anderes geschrieben wird -
// die HT16K33 halten ihren Inhalt selbst, auch ueber einen
// Reset des ESP hinweg.

void Application::showNextText()
{
    ensureDisplayReady();

    // Schutz gegen einen RTC-Wert aus einer aelteren Version
    // mit mehr Texten
    if (_state.textIndex >= TEXT_COUNT)
        _state.textIndex = 0;

    DebugSerial.printf("Text %u/%u\n", _state.textIndex + 1, TEXT_COUNT);

    _display.show(REFLECTION_TEXTS[_state.textIndex]);

    _state.textIndex = (_state.textIndex + 1) % TEXT_COUNT;
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
            DebugSerial.println("(keine Aktion)");
            break;

        case InputEvent::BT2:
            DebugSerial.println("(keine Aktion)");
            break;

        case InputEvent::BT3:
            DebugSerial.println("(keine Aktion)");
            break;

        case InputEvent::BT4:
            DebugSerial.println("(keine Aktion)");
            break;

        case InputEvent::BT5:
            DebugSerial.println("Power Switch umschalten");
            togglePowerSwitch();
            break;

        case InputEvent::BT6:
            showNextText();
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

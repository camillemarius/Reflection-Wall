#include "Application.h"
#include "I2CMasterControl.h"
#include "pinMapping.h"

#include "DebugLogger.h"
#include "BufferTest.h"

#include <ESP8266WiFi.h>
#include <Wire.h>

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

    // Temporaere I2C-Diagnose: meldet Ruhepegel und Scan-
    // Ergebnis und markiert jeden Schritt, damit bei einem
    // Haenger die letzte Zeile zeigt, wo es stehen blieb.
    constexpr bool I2C_DIAG = true;

    // Abnahmetest fuer den neuen I2C-Buffer (PCA9517A), siehe
    // BufferTest.h. Hat Vorrang vor allen anderen Testmodi.
    // Fuer den Normalbetrieb auf false.
    constexpr bool BUFFER_TEST = true;

    // Temporaerer Test: statt zu schlafen alle 2 s einen neuen
    // Text schreiben, um den Bus unter Dauerlast zu beobachten.
    constexpr bool DISPLAY_CYCLE_TEST = true;

    // Temporaerer Oszi-Test: spricht endlos immer dieselbe
    // Adresse an (nur Adressbyte + ACK/NACK + STOP), damit jede
    // Aufnahme mit und ohne LTC4316 dasselbe Bitmuster zeigt.
    // Hat Vorrang vor Diagnose und DISPLAY_CYCLE_TEST.
    //
    // Trigger am Oszi: IN1 (SDA), fallende Flanke, ~2.5 V,
    // SINGLE oder NORMAL. Pro Periode gibt es genau ein START.
    constexpr bool I2C_PROBE_TEST = true;

    // Zieladresse. 0x70 (Master-Seite) antwortet mit beiden
    // LTC4316 zuverlaessig. Jetzt die uebersetzte Seite:
    // 0x69 = Modul hinter dem zweiten LTC4316 (nativ 0x71,
    // XOR 0x18) -> Adressbyte 0xD2 (1101 001 + W).
    constexpr uint8_t PROBE_ADDRESS = 0x71;

    // Pause zwischen zwei Zugriffen. Lang genug, dass am Oszi
    // nur ein Paket im Bild ist und der Trigger eindeutig bleibt.
    constexpr unsigned long PROBE_PERIOD_MS = 20;

    // Zusammenfassung auf der Konsole alle N Zugriffe
    constexpr uint16_t PROBE_REPORT_EVERY = 50;

    [[noreturn]] void runI2CProbeLoop()
    {
        DebugSerial.printf("\n[PROBE] Endlostest auf Adresse 0x%02X, alle %lu ms\n",
                           PROBE_ADDRESS, PROBE_PERIOD_MS);

        // Bus bleibt fuer die ganze Messung beim ESP - kein
        // Umschalten des Analog Switch zwischen den Paketen.
        I2CMasterControl::enable();

        DebugSerial.printf("[PROBE] Bus idle: %s\n",
                           I2CMasterControl::waitForIdleBus() ? "ja" : "NEIN (Timeout)");
        Serial.flush();

        uint32_t total = 0;
        uint16_t codeCount[5] = { 0, 0, 0, 0, 0 };   // 0 = ACK, 1..4 Fehler

        for (;;)
        {
            Wire.beginTransmission(PROBE_ADDRESS);
            const uint8_t code = Wire.endTransmission();

            codeCount[code <= 4 ? code : 4]++;
            total++;

            if (total % PROBE_REPORT_EVERY == 0)
            {
                DebugSerial.printf("[PROBE] #%lu  ACK=%u  NACK-Adr=%u  NACK-Daten=%u  Bus/Timeout=%u  (letzter Code %u)\n",
                                   (unsigned long)total,
                                   codeCount[0], codeCount[2], codeCount[3], codeCount[4],
                                   code);

                for (uint16_t& count : codeCount)
                    count = 0;
            }

            delay(PROBE_PERIOD_MS);
        }
    }

    void diagStep(const char* step)
    {
        if (!I2C_DIAG)
            return;

        DebugSerial.printf("[DIAG] %s\n", step);
        Serial.flush();
    }

    void diagBusLevels(const char* label)
    {
        DebugSerial.printf("[DIAG] %s: SDA=%d SCL=%d GPIO15=%d\n",
                           label,
                           digitalRead(Pins::I2C_SDA),
                           digitalRead(Pins::I2C_SCL),
                           digitalRead(Pins::I2C_MASTER_SEL));
        Serial.flush();
    }

    // Erwartete Teilnehmer: Expander plus die zwoelf Module aus
    // Display.cpp. Muss nachgezogen werden, wenn sich dort eine
    // Adresse aendert.
    constexpr uint8_t EXPECTED_ADDRESSES[] =
    {
        0x20,
        0x70, 0x71, 0x72,
        0x73, 0x74, 0x75,
        0x76, 0x77, 0x7F,
        0x79, 0x7B, 0x7D
    };

    bool isExpected(uint8_t address)
    {
        for (uint8_t expected : EXPECTED_ADDRESSES)
            if (expected == address)
                return true;

        return false;
    }

    // Ein Scan-Durchlauf als drei Zeilen: gefunden, fehlend,
    // unerwartet. Unerwartete Adressen deuten auf Bitfehler hin.
    //
    // Gescannt wird bewusst auch der reservierte Bereich
    // 0x78-0x7F: ein falsch eingestellter LTC4316 kann ein
    // Modul genau dorthin uebersetzen.
    void scanSummary(uint8_t pass)
    {
        bool found[128] = { false };

        for (uint8_t address = 0x01; address <= 0x7F; address++)
        {
            Wire.beginTransmission(address);
            found[address] = (Wire.endTransmission() == 0);
        }

        uint8_t foundCount = 0;
        uint8_t missingCount = 0;
        uint8_t unexpectedCount = 0;

        DebugSerial.printf("[I2C] Scan %u  Gefunden  :", pass);
        for (uint8_t address = 0; address < 128; address++)
            if (found[address])
            {
                DebugSerial.printf(" 0x%02X", address);
                foundCount++;
            }
        DebugSerial.printf("  (%u)\n", foundCount);

        DebugSerial.printf("[I2C] Scan %u  Fehlt     :", pass);
        for (uint8_t expected : EXPECTED_ADDRESSES)
            if (!found[expected])
            {
                DebugSerial.printf(" 0x%02X", expected);
                missingCount++;
            }
        DebugSerial.println(missingCount ? "" : " -");

        DebugSerial.printf("[I2C] Scan %u  Unerwartet:", pass);
        for (uint8_t address = 0; address < 128; address++)
            if (found[address] && !isExpected(address))
            {
                DebugSerial.printf(" 0x%02X", address);
                unexpectedCount++;
            }
        DebugSerial.println(unexpectedCount ? "" : " -");

        Serial.flush();
    }

    void runI2CDiagnostics()
    {
        if (!I2C_DIAG)
            return;

        DebugSerial.println("\n[DIAG] ---- I2C Diagnose ----");
        diagBusLevels("Switch aus (Pi-Seite)");

        I2CMasterControl::enable();
        diagBusLevels("Switch an  (ESP-Seite)");

        DebugSerial.printf("[DIAG] Bus idle: %s\n",
                           I2CMasterControl::waitForIdleBus() ? "ja" : "NEIN (Timeout)");
        Serial.flush();

        // Mehrere Durchlaeufe: ein Teilnehmer, der nur ab und zu
        // fehlt, deutet auf einen grenzwertigen Bus hin.
        constexpr uint8_t SCAN_PASSES = 5;

        for (uint8_t pass = 1; pass <= SCAN_PASSES; pass++)
            scanSummary(pass);

        I2CMasterControl::disable();
        DebugSerial.printf("[DIAG] Bus-Befreiungen (SDA hing LOW): %u\n",
                           I2CMasterControl::recoveryCount());
        DebugSerial.println("[DIAG] ---- Ende Diagnose ----");
        Serial.flush();
    }

    // -----------------------------------------------------
    // Temporaerer Lasttest: Anzeigen dunkel <-> voll an
    // -----------------------------------------------------
    // Prueft, ob der Bus nur unter LED-Last ausfaellt. Die
    // Anzeigen ziehen im Multiplex pulsierend Strom ueber die
    // GND-Pins der Steckverbinder; ein daraus entstehender
    // Masseversatz / Stoerspitzen wuerden sich hier als Unter-
    // schied zwischen den Phasen "dunkel" und "hell" zeigen.
    //
    // Laeuft endlos, damit waehrend der hellen Phase in Ruhe
    // am Oszi gemessen werden kann (z.B. GND letztes Board
    // gegen GND Hauptboard).
    // Hat Vorrang vor Diagnose und DISPLAY_CYCLE_TEST.
    constexpr bool I2C_LOAD_TEST = true;

    constexpr uint8_t LOAD_SCANS_PER_PHASE = 5;
    constexpr unsigned long LOAD_SCAN_INTERVAL_MS = 1000;

    // Die helle Phase bleibt kurz und gedimmt - sie soll nur
    // zeigen, ob der Bus unter LED-Last haelt, nicht blenden.
    constexpr uint8_t LOAD_LIT_SCANS = 2;
    constexpr unsigned long LOAD_LIT_INTERVAL_MS = 500;

    // Adressbereich, der als HT16K33 behandelt wird: nativ
    // 0x70-0x77, uebersetzt 0x79-0x7F. Nach unten bis 0x58
    // offen, damit ein falsch eingestellter LTC4316 trotzdem
    // auffaellt. Bewusst ohne 0x20-0x27 (Expander) und
    // 0x50-0x57 (FeRAM) - ein Schreibzugriff wuerde dort
    // Ausgaenge schalten bzw. Speicher ueberschreiben.
    constexpr uint8_t LOAD_FIRST = 0x58;
    constexpr uint8_t LOAD_LAST = 0x7F;

    // Liegt im Bereich, ist aber kein HT16K33
    constexpr uint8_t LOAD_SKIP_BH1750 = 0x5C;

    constexpr uint8_t LOAD_WRITE_ATTEMPTS = 3;

    // Schreibt einen Zugriff mit Wiederholung, gibt den letzten
    // Fehlercode zurueck (0 = ok).
    uint8_t loadWrite(uint8_t address, const uint8_t* data, uint8_t length)
    {
        uint8_t code = 0;

        for (uint8_t attempt = 0; attempt < LOAD_WRITE_ATTEMPTS; attempt++)
        {
            Wire.beginTransmission(address);
            Wire.write(data, length);
            code = Wire.endTransmission();

            if (code == 0)
                break;
        }

        return code;
    }

    // Alle Segmente an (gedimmt) oder Anzeige aus.
    void loadSetDisplays(const bool* targets, bool on)
    {
        static const uint8_t OSC_ON[]      = { 0x21 };
        static const uint8_t DISPLAY_ON[]  = { 0x81 };
        static const uint8_t DISPLAY_OFF[] = { 0x80 };
        static const uint8_t DIMMED[]      = { 0xE0 | HT16K33::DEFAULT_BRIGHTNESS };

        uint8_t allSegments[1 + HT16K33::BUFFER_SIZE];
        allSegments[0] = 0x00;
        memset(allSegments + 1, 0xFF, HT16K33::BUFFER_SIZE);

        uint8_t ok = 0;

        DebugSerial.printf("[LOAD] Anzeigen %s:", on ? "AN (alle Segmente)" : "AUS");

        for (uint8_t address = LOAD_FIRST; address <= LOAD_LAST; address++)
        {
            if (!targets[address])
                continue;

            uint8_t code;

            if (on)
            {
                code = loadWrite(address, OSC_ON, sizeof(OSC_ON));
                if (code == 0) code = loadWrite(address, allSegments, sizeof(allSegments));
                if (code == 0) code = loadWrite(address, DIMMED, sizeof(DIMMED));
                if (code == 0) code = loadWrite(address, DISPLAY_ON, sizeof(DISPLAY_ON));
            }
            else
            {
                code = loadWrite(address, DISPLAY_OFF, sizeof(DISPLAY_OFF));
            }

            if (code == 0)
                ok++;
            else
                DebugSerial.printf(" 0x%02X:Fehler%u", address, code);
        }

        DebugSerial.printf("  -> %u ok\n", ok);
        Serial.flush();
    }

    // Ein Scan als eine Zeile: Anzahl, fehlende und
    // unerwartete Adressen.
    void loadScan(const char* phase, uint8_t index, uint8_t total = LOAD_SCANS_PER_PHASE)
    {
        bool found[128] = { false };
        uint8_t count = 0;

        for (uint8_t address = 0x01; address <= 0x7F; address++)
        {
            Wire.beginTransmission(address);
            found[address] = (Wire.endTransmission() == 0);
            count += found[address] ? 1 : 0;
        }

        DebugSerial.printf("[LOAD] %-6s %u/%u: %2u gefunden:",
                           phase, index, total, count);

        // Explizit auflisten, damit niemand aus "fehlt" auf die
        // gefundenen Adressen zurueckrechnen muss
        for (uint8_t address = 0; address < 128; address++)
            if (found[address])
                DebugSerial.printf(" 0x%02X", address);

        DebugSerial.print(" | fehlt:");

        bool any = false;
        for (uint8_t expected : EXPECTED_ADDRESSES)
            if (!found[expected])
            {
                DebugSerial.printf(" 0x%02X", expected);
                any = true;
            }
        if (!any)
            DebugSerial.print(" -");

        DebugSerial.print(" | unerwartet:");

        any = false;
        for (uint8_t address = 0; address < 128; address++)
            if (found[address] && !isExpected(address))
            {
                DebugSerial.printf(" 0x%02X", address);
                any = true;
            }
        if (!any)
            DebugSerial.print(" -");

        DebugSerial.println();
        Serial.flush();
    }

    [[noreturn]] void runI2CLoadTest()
    {
        DebugSerial.println("\n[LOAD] ---- Lasttest: Anzeigen dunkel / hell ----");

        I2CMasterControl::enable();

        DebugSerial.printf("[LOAD] Bus idle: %s\n",
                           I2CMasterControl::waitForIdleBus() ? "ja" : "NEIN (Timeout)");

        // Ziele: alle erwarteten Anzeigen plus alles, was im
        // HT16K33-Bereich antwortet (z.B. ein Modul, das hinter
        // dem Translator auf einer noch nicht eingetragenen
        // Adresse erscheint).
        bool targets[128] = { false };

        for (uint8_t expected : EXPECTED_ADDRESSES)
            if (expected >= LOAD_FIRST && expected <= LOAD_LAST)
                targets[expected] = true;

        for (uint8_t address = LOAD_FIRST; address <= LOAD_LAST; address++)
        {
            Wire.beginTransmission(address);
            if (Wire.endTransmission() == 0)
                targets[address] = true;
        }

        targets[LOAD_SKIP_BH1750] = false;

        for (uint32_t round = 1; ; round++)
        {
            DebugSerial.printf("\n[LOAD] === Runde %lu ===\n", (unsigned long)round);

            loadSetDisplays(targets, false);
            for (uint8_t i = 1; i <= LOAD_SCANS_PER_PHASE; i++)
            {
                delay(LOAD_SCAN_INTERVAL_MS);
                loadScan("dunkel", i);
            }

            loadSetDisplays(targets, true);
            for (uint8_t i = 1; i <= LOAD_LIT_SCANS; i++)
            {
                delay(LOAD_LIT_INTERVAL_MS);
                loadScan("hell", i, LOAD_LIT_SCANS);
            }
        }
    }

    // Loescht den Anzeige-RAM aller HT16K33 und schaltet die
    // Anzeigen aus, damit waehrend einer Messung kein LED-Strom
    // fliesst. Nur fuer Testmodi: im Normalbetrieb behalten die
    // HT16K33 ihren Text bewusst ueber den Reset hinweg.
    void blankAllDisplays()
    {
        static const uint8_t DISPLAY_OFF[] = { 0x80 };

        uint8_t emptyRam[1 + HT16K33::BUFFER_SIZE] = { 0 };

        uint8_t ok = 0;
        uint8_t failed = 0;

        DebugSerial.print("[SETUP] Anzeigen leeren:");

        for (uint8_t address = LOAD_FIRST; address <= LOAD_LAST; address++)
        {
            Wire.beginTransmission(address);
            const bool present = (Wire.endTransmission() == 0);

            if (address == LOAD_SKIP_BH1750)
                continue;

            if (!present && !isExpected(address))
                continue;

            uint8_t code = loadWrite(address, emptyRam, sizeof(emptyRam));
            if (code == 0)
                code = loadWrite(address, DISPLAY_OFF, sizeof(DISPLAY_OFF));

            if (code == 0)
            {
                ok++;
            }
            else
            {
                failed++;
                DebugSerial.printf(" 0x%02X:Fehler%u", address, code);
            }
        }

        DebugSerial.printf("  -> %u geleert, %u fehlgeschlagen\n", ok, failed);
        Serial.flush();
    }

    // -----------------------------------------------------
    // Temporaerer Lauflicht-Test: ein einzelnes Segment
    // -----------------------------------------------------
    // Ein Segment wandert Stelle fuer Stelle von links nach
    // rechts durch alle Module, Zeile fuer Zeile. So ist auf
    // einen Blick zu sehen, welches Modul erreichbar ist und ob
    // die Reihenfolge im Raster stimmt. Hat Vorrang vor allen
    // anderen Testmodi.
    constexpr bool SEGMENT_SWEEP_TEST = true;

    // Reihenfolge wie in display.cpp: Zeile fuer Zeile, links
    // nach rechts
    constexpr uint8_t SWEEP_ORDER[] =
    {
        0x70, 0x71, 0x72,
        0x73, 0x74, 0x75,
        0x76, 0x77, 0x7F,
        0x79, 0x7B, 0x7D
    };

    // Welcher ROW-Ausgang leuchtet: Bit n = ROWn (Low-Byte
    // ROW0-7, High-Byte ROW8-15). ROW7 statt ROW0, weil ROW0-2
    // zugleich die Adresspins A2-A0 des HT16K33 sind.
    constexpr uint16_t SWEEP_SEGMENT = 1u << 7;   // ROW7

    constexpr unsigned long SWEEP_STEP_MS = 150;

    // Ruhepause nach jedem Durchlauf: kein Buszugriff, alle
    // Anzeigen leer - Zeit zum Messen von Pegeln und Speisung
    constexpr unsigned long SWEEP_PAUSE_MS = 10000;

    // Schreibt den ganzen Anzeige-RAM eines Moduls: nur an
    // Stelle `digit` ist das Segment an, alles andere aus.
    // digit >= CHARS_PER_MODULE loescht das Modul.
    uint8_t sweepWrite(uint8_t address, uint8_t digit)
    {
        uint8_t ram[1 + HT16K33::BUFFER_SIZE] = { 0 };

        if (digit < HT16K33::CHARS_PER_MODULE)
        {
            ram[1 + digit * 2]     = SWEEP_SEGMENT & 0xFF;
            ram[1 + digit * 2 + 1] = SWEEP_SEGMENT >> 8;
        }

        return loadWrite(address, ram, sizeof(ram));
    }

    // Vor jedem Modul Oszillator, Helligkeit und Anzeige erneut
    // einschalten. false: nur einmal beim Start (zeigt, ob ein
    // Modul seine Einstellung verliert). true: jedes Mal neu
    // (bringt ein solches Modul wieder zum Leuchten).
    constexpr bool SWEEP_REINIT_EACH_MODULE = true;

    // Nach jedem Schritt den Anzeige-RAM zuruecklesen und mit
    // dem Geschriebenen vergleichen. Ein "ok" beim Schreiben
    // heisst nur, dass die Bytes quittiert wurden - nicht, dass
    // sie unverfaelscht angekommen sind.
    constexpr bool SWEEP_VERIFY = false;

    // Schickt Oszillator ein, Helligkeit, Anzeige ein. Bei einem
    // Fehler steht in failedCommand der Befehl, der scheiterte.
    uint8_t sweepInit(uint8_t address, uint8_t& failedCommand)
    {
        const uint8_t commands[] =
        {
            0x21,                                   // Oszillator ein
            (uint8_t)(0xE0 | HT16K33::DEFAULT_BRIGHTNESS),
            0x81                                    // Anzeige ein
        };

        for (uint8_t command : commands)
        {
            const uint8_t code = loadWrite(address, &command, 1);

            if (code != 0)
            {
                failedCommand = command;
                return code;
            }
        }

        return 0;
    }

    uint8_t sweepInit(uint8_t address)
    {
        uint8_t ignored;
        return sweepInit(address, ignored);
    }

    // Liest den Anzeige-RAM (16 Byte ab Adresse 0x00) zurueck
    // und vergleicht mit dem Muster fuer `digit`. Gibt true
    // zurueck, wenn alles stimmt; bei Abweichung landet das
    // erste falsche Byte in badIndex/badValue.
    bool sweepVerify(uint8_t address, uint8_t digit, uint8_t& badIndex, int& badValue)
    {
        Wire.beginTransmission(address);
        Wire.write((uint8_t)0x00);

        if (Wire.endTransmission(false) != 0)
        {
            badIndex = 0xFF;
            badValue = -1;
            return false;
        }

        const uint8_t count = Wire.requestFrom(address, (uint8_t)HT16K33::BUFFER_SIZE);

        for (uint8_t i = 0; i < HT16K33::BUFFER_SIZE; i++)
        {
            uint8_t expected = 0;

            if (digit < HT16K33::CHARS_PER_MODULE)
            {
                if (i == digit * 2)     expected = SWEEP_SEGMENT & 0xFF;
                if (i == digit * 2 + 1) expected = SWEEP_SEGMENT >> 8;
            }

            const int value = (i < count) ? Wire.read() : -1;

            if (value != expected)
            {
                badIndex = i;
                badValue = value;

                while (Wire.available())
                    Wire.read();

                return false;
            }
        }

        return true;
    }

    [[noreturn]] void runSegmentSweep()
    {
        constexpr uint8_t CLEAR = HT16K33::CHARS_PER_MODULE;

        DebugSerial.println("\n[SWEEP] ---- Lauflicht: ein Segment von links nach rechts ----");

        I2CMasterControl::enable();

        // Alle Module einschalten und leeren
        for (uint8_t address : SWEEP_ORDER)
        {
            uint8_t code = sweepInit(address);
            if (code == 0) code = sweepWrite(address, CLEAR);

            DebugSerial.printf("[SWEEP] Init 0x%02X: %s\n",
                               address, code == 0 ? "ok" : "FEHLER");
        }
        Serial.flush();

        for (uint32_t round = 1; ; round++)
        {
            DebugSerial.printf("\n[SWEEP] Durchlauf %lu\n", (unsigned long)round);

            for (uint8_t address : SWEEP_ORDER)
            {
                uint8_t failedSteps = 0;
                uint8_t verifyFailed = 0;
                uint8_t firstBadIndex = 0;
                int firstBadValue = 0;

                // Getrennt erfassen: scheitern die Einstellbefehle
                // (1 Byte) oder die RAM-Schreibzugriffe (17 Byte)?
                uint8_t initCode = 0;
                uint8_t initCommand = 0;
                uint8_t ramFailed = 0;
                uint8_t ramFirstCode = 0;

                if (SWEEP_REINIT_EACH_MODULE)
                {
                    initCode = sweepInit(address, initCommand);
                    if (initCode != 0)
                        failedSteps++;
                }

                for (uint8_t digit = 0; digit < HT16K33::CHARS_PER_MODULE; digit++)
                {
                    const uint8_t ramCode = sweepWrite(address, digit);

                    if (ramCode != 0)
                    {
                        if (ramFailed == 0)
                            ramFirstCode = ramCode;
                        ramFailed++;
                        failedSteps++;
                    }

                    uint8_t badIndex;
                    int badValue;

                    if (SWEEP_VERIFY && !sweepVerify(address, digit, badIndex, badValue))
                    {
                        if (verifyFailed == 0)
                        {
                            firstBadIndex = badIndex;
                            firstBadValue = badValue;
                        }
                        verifyFailed++;
                    }

                    delay(SWEEP_STEP_MS);
                }

                // Segment verlaesst das Modul
                if (sweepWrite(address, CLEAR) != 0)
                    failedSteps++;

                DebugSerial.printf("[SWEEP] 0x%02X: %s", address,
                                   failedSteps == 0 ? "ok" : "Schreibfehler");

                // Fehlercodes: 2 = NACK Adresse, 3 = NACK Daten,
                // 4 = Bus belegt / SDA war LOW
                if (SWEEP_REINIT_EACH_MODULE)
                {
                    if (initCode == 0)
                        DebugSerial.print(" | Init ok");
                    else
                        DebugSerial.printf(" | Init Befehl 0x%02X Code %u", initCommand, initCode);
                }

                if (ramFailed == 0)
                    DebugSerial.print(" | RAM ok");
                else
                    DebugSerial.printf(" | RAM %u/%u Code %u",
                                       ramFailed, HT16K33::CHARS_PER_MODULE, ramFirstCode);

                if (SWEEP_VERIFY)
                {
                    if (verifyFailed == 0)
                        DebugSerial.print(" | Ruecklesen ok");
                    else if (firstBadIndex == 0xFF)
                        DebugSerial.printf(" | Ruecklesen %u/8 falsch (Zeiger nicht gesetzt)", verifyFailed);
                    else
                        DebugSerial.printf(" | Ruecklesen %u/8 falsch, z.B. Byte %u = %d",
                                           verifyFailed, firstBadIndex, firstBadValue);
                }

                DebugSerial.println();
            }

            DebugSerial.printf("[SWEEP] Pause %lu s - Bus ruhig, Anzeigen leer | SDA=%d SCL=%d\n",
                               SWEEP_PAUSE_MS / 1000,
                               digitalRead(Pins::I2C_SDA), digitalRead(Pins::I2C_SCL));
            Serial.flush();

            delay(SWEEP_PAUSE_MS);
        }
    }

    // -----------------------------------------------------
    // Temporaerer Test: SDA-Hold-Zeit durchprobieren
    // -----------------------------------------------------
    // Stellt nacheinander jede Hold-Zeit aus HOLD_VALUES_US ein
    // (siehe lib/Wire) und spricht pro Wert jeden erwarteten
    // Teilnehmer HOLD_PROBES mal an - reihum, damit eine
    // zeitweise Stoerung alle gleich trifft. Ausgegeben werden
    // nur die Teilnehmer, die nicht jedes Mal geantwortet haben.
    // 0 us entspricht dem Verhalten der Core-Bibliothek und
    // dient als Vergleich. Laeuft endlos in Runden.
    // Hat Vorrang vor allen anderen Testmodi.
    constexpr bool I2C_HOLD_TEST = false;

    constexpr uint32_t HOLD_VALUES_US[] = { 0, 2, 5, 10, 20, 30, 40 };

    constexpr uint16_t HOLD_PROBES = 50;
    constexpr unsigned long HOLD_PROBE_PERIOD_MS = 2;

    constexpr uint8_t EXPECTED_COUNT = sizeof(EXPECTED_ADDRESSES) / sizeof(EXPECTED_ADDRESSES[0]);

    void holdTestOneValue(uint32_t holdUs)
    {
        Wire.setSdaHold(holdUs);

        uint16_t acks[EXPECTED_COUNT] = { 0 };
        uint16_t busErrors = 0;
        uint16_t recoveriesOk = 0;
        uint16_t recoveriesFailed = 0;

        for (uint16_t i = 0; i < HOLD_PROBES; i++)
        {
            bool busErrorThisRound = false;

            for (uint8_t n = 0; n < EXPECTED_COUNT; n++)
            {
                Wire.beginTransmission(EXPECTED_ADDRESSES[n]);
                const uint8_t code = Wire.endTransmission();

                if (code == 0)
                    acks[n]++;
                else if (code == 4)
                {
                    busErrors++;
                    busErrorThisRound = true;
                }
            }

            // Code 4 heisst: SDA war beim START schon LOW. Haengt
            // ein Slave mitten in einem Byte, befreien ihn 9 SCL-
            // Pulse + STOP. Bleibt SDA trotzdem LOW, haelt etwas
            // die Leitung hart fest.
            if (busErrorThisRound && digitalRead(Pins::I2C_SDA) == LOW)
            {
                if (I2CMasterControl::recoverBus())
                    recoveriesOk++;
                else
                    recoveriesFailed++;

                // recoverBus() richtet Wire neu ein; die Hold-Zeit
                // zur Sicherheit erneut setzen
                Wire.setSdaHold(holdUs);
            }

            delay(HOLD_PROBE_PERIOD_MS);
        }

        uint8_t complete = 0;
        for (uint8_t n = 0; n < EXPECTED_COUNT; n++)
            complete += (acks[n] == HOLD_PROBES) ? 1 : 0;

        DebugSerial.printf("[HOLD] %2lu us | %2u/%u immer ACK | Bus %3u | Befreiung ok %u / fehlgeschlagen %u | SDA=%d SCL=%d | Aussetzer:",
                           (unsigned long)holdUs, complete, EXPECTED_COUNT, busErrors,
                           recoveriesOk, recoveriesFailed,
                           digitalRead(Pins::I2C_SDA), digitalRead(Pins::I2C_SCL));

        bool any = false;
        for (uint8_t n = 0; n < EXPECTED_COUNT; n++)
            if (acks[n] != HOLD_PROBES)
            {
                DebugSerial.printf(" 0x%02X %u/%u", EXPECTED_ADDRESSES[n], acks[n], HOLD_PROBES);
                any = true;
            }
        if (!any)
            DebugSerial.print(" -");

        // Einmal quer scannen: taucht ein Modul auf einer
        // falschen Adresse auf?
        bool found[128] = { false };

        for (uint8_t address = 0x01; address <= 0x7F; address++)
        {
            Wire.beginTransmission(address);
            found[address] = (Wire.endTransmission() == 0);
        }

        DebugSerial.print(" | unerwartet:");

        any = false;
        for (uint8_t address = 0; address < 128; address++)
            if (found[address] && !isExpected(address))
            {
                DebugSerial.printf(" 0x%02X", address);
                any = true;
            }
        if (!any)
            DebugSerial.print(" -");

        DebugSerial.println();
        Serial.flush();
    }

    [[noreturn]] void runHoldTest()
    {
        DebugSerial.printf("\n[HOLD] ---- SDA-Hold-Zeit: %u Werte, je %u Zugriffe auf jeden der %u Teilnehmer ----\n",
                           (unsigned)(sizeof(HOLD_VALUES_US) / sizeof(HOLD_VALUES_US[0])),
                           HOLD_PROBES, EXPECTED_COUNT);

        for (uint32_t round = 1; ; round++)
        {
            DebugSerial.printf("\n[HOLD] === Runde %lu ===\n", (unsigned long)round);

            for (uint32_t holdUs : HOLD_VALUES_US)
                holdTestOneValue(holdUs);
        }
    }

    // -----------------------------------------------------
    // Temporaerer Test: welche Datenbytes werden abgelehnt?
    // -----------------------------------------------------
    // 0x78 und 0x7A quittieren ihre Adresse, lehnen aber den
    // Befehl 0x21 ab (NACK auf das Datenbyte), waehrend RAM-
    // Zugriffe mit 0x00 durchgehen. Dieser Test schickt jedes
    // Byte aus CMD_BYTES einzeln an jedes Modul aus CMD_TARGETS
    // und zaehlt die ACKs. Das Muster zeigt, ob es an einem
    // bestimmten Bit liegt.
    // Hat Vorrang vor allen anderen Testmodi.
    constexpr bool CMD_MATRIX_TEST = true;

    // 0x77 (Master-Seite) und 0x79/0x7B (hinter Translator,
    // funktionieren) als Vergleich; frueher fielen 0x78/0x7A aus (nativ A0 = 0)
    constexpr uint8_t CMD_TARGETS[] = { 0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77, 0x7F, 0x79, 0x7B, 0x7D };

    // Nur harmlose Befehle: RAM-Zeiger setzen, Oszillator und
    // Anzeige aus/ein, Helligkeit. Die Reihenfolge endet mit
    // "alles ein", damit die Anzeigen danach bereit sind.
    constexpr uint8_t CMD_BYTES[] =
    {
        0x00,   // RAM-Zeiger 0      0000 0000
        0x01,   // RAM-Zeiger 1      0000 0001
        0x02,   // RAM-Zeiger 2      0000 0010
        0x04,   // RAM-Zeiger 4      0000 0100
        0x08,   // RAM-Zeiger 8      0000 1000
        0x0F,   // RAM-Zeiger 15     0000 1111
        0x20,   // Oszillator aus    0010 0000
        0x80,   // Anzeige aus       1000 0000
        0xE0,   // Helligkeit 0      1110 0000
        0xE4,   // Helligkeit 4      1110 0100
        0x21,   // Oszillator ein    0010 0001
        0x81    // Anzeige ein       1000 0001
    };

    constexpr uint8_t CMD_REPEATS = 20;
    constexpr unsigned long CMD_PAUSE_MS = 1000;

    // Jede Runde laeuft mit der naechsten Hold-Zeit aus dieser
    // Liste (siehe lib/Wire)
    constexpr uint32_t CMD_HOLD_VALUES_US[] = { 10 };
    constexpr uint8_t CMD_HOLD_COUNT = sizeof(CMD_HOLD_VALUES_US) / sizeof(CMD_HOLD_VALUES_US[0]);

    [[noreturn]] void runCommandMatrix()
    {
        DebugSerial.printf("\n[CMD] ---- Welche Datenbytes werden quittiert? je %u Versuche, ohne Wiederholung ----\n",
                           CMD_REPEATS);

        I2CMasterControl::enable();

        for (uint32_t round = 1; ; round++)
        {
            // Jede Runde mit der naechsten Hold-Zeit
            const uint32_t holdUs = CMD_HOLD_VALUES_US[(round - 1) % CMD_HOLD_COUNT];
            Wire.setSdaHold(holdUs);

            DebugSerial.printf("\n[CMD] === Runde %lu, SDA-Hold %lu us ===\n[CMD] Adr  |",
                               (unsigned long)round, (unsigned long)holdUs);

            for (uint8_t command : CMD_BYTES)
                DebugSerial.printf("  %02X", command);

            DebugSerial.println();

            for (uint8_t address : CMD_TARGETS)
            {
                DebugSerial.printf("[CMD] 0x%02X |", address);

                for (uint8_t command : CMD_BYTES)
                {
                    uint8_t acks = 0;
                    uint8_t lastError = 0;

                    // Bewusst ohne loadWrite(): keine Wiederholung,
                    // jeder Versuch zaehlt einzeln
                    for (uint8_t i = 0; i < CMD_REPEATS; i++)
                    {
                        Wire.beginTransmission(address);
                        Wire.write(command);
                        const uint8_t code = Wire.endTransmission();

                        if (code == 0)
                            acks++;
                        else
                            lastError = code;
                    }

                    // "ok" = immer ACK, sonst Anzahl ACK und der
                    // letzte Fehlercode als Buchstabe:
                    // a = NACK Adresse, d = NACK Daten, b = Bus
                    if (acks == CMD_REPEATS)
                        DebugSerial.print("  ok");
                    else
                        DebugSerial.printf(" %2u%c", acks,
                                           lastError == 2 ? 'a' :
                                           lastError == 3 ? 'd' :
                                           lastError == 4 ? 'b' : '?');
                }

                DebugSerial.println();
            }

            // Zwei Bytes: RAM-Zeiger 0x00, dann ein Datenbyte. Zeigt,
            // ob das Problem nur das erste Byte (Befehl) betrifft
            // oder jedes Byte mit Bit 0 = 1.
            static const uint8_t RAM_DATA[] = { 0x00, 0x01, 0x02, 0x80, 0x81, 0xFE, 0xFF };

            // Anzeigen fuer den RAM-Teil ausschalten (0x80, Bit 0 = 0
            // geht ueberall durch), sonst blitzen die Testmuster in
            // Stelle 0 auf
            for (uint8_t address : CMD_TARGETS)
            {
                Wire.beginTransmission(address);
                Wire.write((uint8_t)0x80);
                Wire.endTransmission();
            }

            DebugSerial.print("[CMD] 00+xx|");
            for (uint8_t data : RAM_DATA)
                DebugSerial.printf("  %02X", data);
            DebugSerial.println();

            for (uint8_t address : CMD_TARGETS)
            {
                DebugSerial.printf("[CMD] 0x%02X |", address);

                for (uint8_t data : RAM_DATA)
                {
                    uint8_t acks = 0;
                    uint8_t lastError = 0;

                    for (uint8_t i = 0; i < CMD_REPEATS; i++)
                    {
                        Wire.beginTransmission(address);
                        Wire.write((uint8_t)0x00);
                        Wire.write(data);
                        const uint8_t code = Wire.endTransmission();

                        if (code == 0)
                            acks++;
                        else
                            lastError = code;
                    }

                    if (acks == CMD_REPEATS)
                        DebugSerial.print("  ok");
                    else
                        DebugSerial.printf(" %2u%c", acks,
                                           lastError == 2 ? 'a' :
                                           lastError == 3 ? 'd' :
                                           lastError == 4 ? 'b' : '?');
                }

                // Ganzen Anzeige-RAM loeschen: der Test schaltet die
                // Anzeige ein, sonst leuchtet der zufaellige RAM-
                // Inhalt nach dem Einschalten. Nur Nullen - die
                // gehen auch bei 0x78/0x7A sauber durch.
                sweepWrite(address, HT16K33::CHARS_PER_MODULE);

                DebugSerial.println();
            }

            DebugSerial.printf("[CMD] Legende: ok = %u/%u ACK, sonst ACK-Anzahl + a=NACK Adresse, d=NACK Daten, b=Bus belegt\n",
                               CMD_REPEATS, CMD_REPEATS);
            DebugSerial.printf("[CMD] Pause %lu s | SDA=%d SCL=%d\n",
                               CMD_PAUSE_MS / 1000,
                               digitalRead(Pins::I2C_SDA), digitalRead(Pins::I2C_SCL));
            Serial.flush();

            delay(CMD_PAUSE_MS);
        }
    }

    // -----------------------------------------------------
    // Temporaerer Test: kommen Daten trotz NACK richtig an?
    // -----------------------------------------------------
    // Bei 0x78/0x7A fehlt das ACK nach Bytes mit Bit 0 = 1, die
    // Befehle werden aber ausgefuehrt. Hier senden alle Module
    // ihre Daten vollstaendig, auch wenn ein NACK kommt
    // (Wire.setIgnoreDataNack). Alle 12 Module zeigen dasselbe
    // Muster - weichen 0x78/0x7A von den Nachbarn ab, kommen die
    // Daten verfaelscht an.
    // Hat Vorrang vor allen anderen Testmodi.
    constexpr bool PATTERN_TEST = false;

    constexpr unsigned long PATTERN_SHOW_MS = 6000;
    constexpr unsigned long PATTERN_OFF_MS = 3000;

    struct Pattern
    {
        const char* name;
        uint16_t segments;   // Bit n = ROWn, gleich fuer alle 8 Stellen
    };

    constexpr Pattern PATTERNS[] =
    {
        { "alle Segmente (Bit 0 = 1 in beiden Bytes)",       0xFFFF },
        { "Mittelstrich '-' (0x0101, nur Bit 0 der Bytes)", 0x0101 },
        { "alles ausser Mittelstrich (0xFEFE, Bit 0 = 0)",   0xFEFE }
    };

    // Schickt ein Byte-Paket und gibt den Code zurueck; NACKs auf
    // Daten brechen dabei nicht ab
    uint8_t patternSend(uint8_t address, const uint8_t* data, uint8_t length)
    {
        Wire.beginTransmission(address);
        Wire.write(data, length);
        return Wire.endTransmission();
    }

    [[noreturn]] void runPatternTest()
    {
        DebugSerial.println("\n[PAT] ---- Muster auf allen Modulen, NACK auf Daten wird ignoriert ----");

        I2CMasterControl::enable();
        Wire.setIgnoreDataNack(true);

        for (uint32_t round = 1; ; round++)
        {
            for (const Pattern& pattern : PATTERNS)
            {
                DebugSerial.printf("\n[PAT] Runde %lu: %s\n", (unsigned long)round, pattern.name);

                uint8_t ram[1 + HT16K33::BUFFER_SIZE];
                ram[0] = 0x00;
                for (uint8_t digit = 0; digit < HT16K33::CHARS_PER_MODULE; digit++)
                {
                    ram[1 + digit * 2]     = pattern.segments & 0xFF;
                    ram[1 + digit * 2 + 1] = pattern.segments >> 8;
                }

                for (uint8_t address : SWEEP_ORDER)
                {
                    // Einstellbefehle einzeln, jeder wird gesendet -
                    // egal ob der vorherige quittiert wurde
                    const uint8_t osc  = 0x21;
                    const uint8_t dim  = 0xE0 | HT16K33::DEFAULT_BRIGHTNESS;
                    const uint8_t on   = 0x81;

                    const uint8_t cOsc = patternSend(address, &osc, 1);
                    const uint8_t cDim = patternSend(address, &dim, 1);
                    const uint8_t cRam = patternSend(address, ram, sizeof(ram));
                    const uint8_t cOn  = patternSend(address, &on, 1);

                    DebugSerial.printf("[PAT] 0x%02X: Osc %u  Dim %u  RAM %u  On %u\n",
                                       address, cOsc, cDim, cRam, cOn);
                }

                DebugSerial.printf("[PAT] %lu s anzeigen - sehen 0x78 und 0x7A aus wie die Nachbarn?\n",
                                   PATTERN_SHOW_MS / 1000);
                Serial.flush();
                delay(PATTERN_SHOW_MS);

                // Alles aus (0x80 hat Bit 0 = 0, geht ueberall durch)
                for (uint8_t address : SWEEP_ORDER)
                {
                    const uint8_t off = 0x80;
                    patternSend(address, &off, 1);
                }

                delay(PATTERN_OFF_MS);
            }
        }
    }

    // -----------------------------------------------------
    // Temporaerer Test: SDA waehrend des ACK aufzeichnen
    // -----------------------------------------------------
    // Der ESP tastet SDA im ACK-Takt nach dem Datenbyte ab
    // (Low-Phase und High-Phase von SCL, je ~1 Sample/us).
    // Vergleich: funktionierende und fehlerhafte Module, Befehl
    // mit Bit 0 = 0 (0x20, danach wieder 0x21 via Matrix) und
    // mit Bit 0 = 1 (0x21). Zeigt, ob der Slave gar nicht
    // quittiert oder ob sein ACK kurz sichtbar ist und dann
    // abgeschnitten wird.
    // Hat Vorrang vor allen anderen Testmodi.
    constexpr bool ACK_TRACE_TEST = true;

    constexpr uint8_t TRACE_TARGETS[] = { 0x77, 0x79, 0x7B, 0x7D, 0x7F };
    constexpr uint8_t TRACE_COMMANDS[] = { 0xE4, 0x81 };   // Bit 0 = 0 / Bit 0 = 1
    constexpr uint8_t TRACE_REPEATS = 2;

    void printTrace(const char* label, uint64_t trace, uint8_t count)
    {
        char text[65];
        for (uint8_t i = 0; i < count && i < 64; i++)
            text[i] = (trace & (1ULL << i)) ? '-' : '_';
        text[count < 64 ? count : 64] = '\0';

        DebugSerial.printf("        %s %s\n", label, text);
    }

    [[noreturn]] void runAckTrace()
    {
        DebugSerial.println("\n[TRC] ---- SDA im ACK-Takt nach dem Datenbyte ('-' = HIGH, '_' = LOW, ~1 us pro Zeichen) ----");

        I2CMasterControl::enable();
        Wire.setAckTrace(true);

        for (uint32_t round = 1; ; round++)
        {
            DebugSerial.printf("\n[TRC] === Runde %lu ===\n", (unsigned long)round);

            for (uint8_t command : TRACE_COMMANDS)
            {
                for (uint8_t address : TRACE_TARGETS)
                {
                    for (uint8_t i = 0; i < TRACE_REPEATS; i++)
                    {
                        Wire.beginTransmission(address);
                        Wire.write(command);
                        const uint8_t code = Wire.endTransmission();

                        // 64 schnelle Samples direkt nach "SCL low"
                        const uint32_t nsPerSample =
                            Wire.ackTraceFastCycles() * (1000000000UL / F_CPU) / 64;

                        DebugSerial.printf("[TRC] 0x%02X Befehl 0x%02X -> Code %u  (%lu ns/Sample)\n",
                                           address, command, code, (unsigned long)nsPerSample);
                        printTrace("SCL low :", Wire.ackTraceLow(), Wire.ackTraceLowCount());
                    }
                }
            }

            Serial.flush();
            delay(3000);
        }
    }

    // -----------------------------------------------------
    // Temporaerer Sichttest: jedes Modul zeigt seine Adresse
    // -----------------------------------------------------
    // Jedes Modul zeigt "ADR xx n": seine I2C-Adresse und einen
    // Zaehler, der alle ID_PERIOD_MS weiterspringt. Ein Modul,
    // das sauber funktioniert, zaehlt sichtbar mit; ein gestoertes
    // bleibt dunkel, zeigt nur Teile oder falsche Zeichen.
    // Gleicher Weg wie im Normalbetrieb (HT16K33::begin/setText),
    // also ohne Sonderbehandlung von NACKs.
    // Hat Vorrang vor allen anderen Testmodi.
    constexpr bool ID_TEST = true;

    constexpr unsigned long ID_PERIOD_MS = 2000;

    [[noreturn]] void runIdTest()
    {
        DebugSerial.println("\n[ID] ---- Jedes Modul zeigt 'ADR <Adresse> <Zaehler>' ----");

        I2CMasterControl::enable();

        constexpr uint8_t COUNT = sizeof(SWEEP_ORDER) / sizeof(SWEEP_ORDER[0]);

        for (uint32_t round = 0; ; round++)
        {
            DebugSerial.printf("\n[ID] Zaehler %lu\n", (unsigned long)(round % 10));

            // Haelt jemand SDA fest, erst befreien: mehrere Runden
            // aus 9 SCL-Pulsen + STOP
            if (digitalRead(Pins::I2C_SDA) == LOW)
            {
                bool freed = false;

                for (uint8_t attempt = 1; attempt <= 5 && !freed; attempt++)
                {
                    freed = I2CMasterControl::recoverBus();
                    DebugSerial.printf("[ID] SDA war LOW - Befreiung %u: %s (SDA=%d SCL=%d)\n",
                                       attempt, freed ? "ok" : "fehlgeschlagen",
                                       digitalRead(Pins::I2C_SDA), digitalRead(Pins::I2C_SCL));
                }
            }

            for (uint8_t n = 0; n < COUNT; n++)
            {
                HT16K33 module(SWEEP_ORDER[n]);

                const int sdaBefore = digitalRead(Pins::I2C_SDA);
                const int sclBefore = digitalRead(Pins::I2C_SCL);

                // Zuerst den Text in den RAM, erst danach einschalten:
                // so leuchtet nie zufaelliger RAM-Inhalt nach dem
                // Einschalten
                char text[9];
                snprintf(text, sizeof(text), "ADR %02X %lu",
                         SWEEP_ORDER[n], (unsigned long)(round % 10));

                module.resetWriteStats();
                module.setText(String(text));
                const uint8_t error = module.lastWriteError();

                // Bei jedem Durchlauf neu einschalten - wie
                // Display::begin() im Normalbetrieb
                module.begin();

                if (error == 0)
                    DebugSerial.printf("[ID] 0x%02X: ok\n", SWEEP_ORDER[n]);
                else
                    DebugSerial.printf("[ID] 0x%02X: FEHLER Code %u (%u Wiederholungen) | vorher SDA=%d SCL=%d, nachher SDA=%d SCL=%d\n",
                                       SWEEP_ORDER[n], error, module.writeRetries(),
                                       sdaBefore, sclBefore,
                                       digitalRead(Pins::I2C_SDA), digitalRead(Pins::I2C_SCL));
            }

            Serial.flush();
            delay(ID_PERIOD_MS);
        }
    }

    // -----------------------------------------------------
    // Temporaerer Oszi-Modus: die kritische SCL-Flanke messen
    // -----------------------------------------------------
    // Wiederholt endlos genau den Zugriff, der fehlschlaegt:
    // SCOPE_ADDRESS + ein Befehl mit Bit 0 = 1. Die interessante
    // Stelle ist die fallende SCL-Flanke direkt vor dem ACK nach
    // diesem Byte. Die Konsole meldet, wie viele us nach dem START
    // sie kommt - diesen Wert am Red Pitaya als Zeitverschiebung
    // einstellen (Trigger: SDA fallend = START).
    // Hat Vorrang vor allen anderen Testmodi.
    constexpr bool SCOPE_TEST = true;

    // 0x7B faellt aus, 0x79 am selben Translator funktioniert -
    // zum Vergleich einfach umstellen
    constexpr uint8_t SCOPE_ADDRESS = 0x7B;
    constexpr uint8_t SCOPE_COMMAND = 0x81;          // Anzeige ein, Bit 0 = 1
    constexpr unsigned long SCOPE_PERIOD_MS = 20;
    constexpr uint16_t SCOPE_REPORT_EVERY = 50;

    [[noreturn]] void runScopeTest()
    {
        DebugSerial.printf("\n[SCOPE] Endlos: Adresse 0x%02X + Befehl 0x%02X, alle %lu ms\n",
                           SCOPE_ADDRESS, SCOPE_COMMAND, SCOPE_PERIOD_MS);
        DebugSerial.println("[SCOPE] Trigger: SDA fallend (START), ~2.5 V, NORMAL");

        I2CMasterControl::enable();

        uint16_t acks = 0, nacks = 0, other = 0;
        uint32_t minUs = UINT32_MAX, maxUs = 0;

        for (uint32_t n = 1; ; n++)
        {
            Wire.beginTransmission(SCOPE_ADDRESS);
            Wire.write(SCOPE_COMMAND);
            const uint8_t code = Wire.endTransmission();

            const uint32_t us = Wire.lastAckFallAfterStartUs();
            if (us < minUs) minUs = us;
            if (us > maxUs) maxUs = us;

            if (code == 0) acks++;
            else if (code == 3) nacks++;
            else other++;

            // Haengt SDA nach einem Fehler, freigeben
            if (digitalRead(Pins::I2C_SDA) == LOW)
                I2CMasterControl::recoverBus();

            if (n % SCOPE_REPORT_EVERY == 0)
            {
                DebugSerial.printf("[SCOPE] #%lu  ACK %u  NACK-Daten %u  andere %u | kritische SCL-Flanke %lu..%lu us nach START\n",
                                   (unsigned long)n, acks, nacks, other,
                                   (unsigned long)minUs, (unsigned long)maxUs);
                acks = nacks = other = 0;
                minUs = UINT32_MAX;
                maxUs = 0;
            }

            delay(SCOPE_PERIOD_MS);
        }
    }
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

    if (SCOPE_TEST)
        runScopeTest();

    if (ID_TEST)
        runIdTest();

    if (ACK_TRACE_TEST)
        runAckTrace();

    if (PATTERN_TEST)
        runPatternTest();

    if (CMD_MATRIX_TEST)
        runCommandMatrix();

    if (I2C_HOLD_TEST)
    {
        // Ohne LED-Last messen
        I2CMasterControl::enable();
        blankAllDisplays();

        runHoldTest();
    }

    if (SEGMENT_SWEEP_TEST)
        runSegmentSweep();

    if (I2C_PROBE_TEST)
    {
        // Messung ohne LED-Last: alle Anzeigen vorher leeren
        I2CMasterControl::enable();
        blankAllDisplays();

        // Einmal alles auflisten, was antwortet - zeigt, auf
        // welcher Adresse ein uebersetztes Modul tatsaechlich
        // liegt, falls die Zieladresse nicht antwortet.
        loadScan("start", 1);

        runI2CProbeLoop();
    }

    if (I2C_LOAD_TEST)
        runI2CLoadTest();

    runI2CDiagnostics();

    diagStep("readExpander()");
    const uint16_t state = readExpander();
    diagStep("readExpander() fertig");

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

    // Testmodus: kein Deep Sleep, alle 2 s der naechste Text.
    // Ein Tastendruck setzt den ESP weiterhin zurueck.
    if (DISPLAY_CYCLE_TEST)
    {
        for (uint32_t round = 1; ; round++)
        {
            DebugSerial.printf("[TEST] Durchlauf %lu: ", (unsigned long)round);
            showNextText();
            Serial.flush();
            delay(6000);
        }
    }

    // Nach dem Einschalten ist die Anzeige leer und die
    // HT16K33 sind unkonfiguriert - hier muss ein Text stehen.
    // Nach einem Reset behalten sie ihren Inhalt, die Anzeige
    // bleibt dann unberuehrt.
    if (_coldBoot)
    {
        diagStep("showNextText()");
        DebugSerial.print("[DISPLAY] ");
        showNextText();
        diagStep("showNextText() fertig");
    }

    for (uint8_t i = 0; i < count; i++)
    {
        DebugSerial.printf("[INPUT] %s -> ", buttonName(events[i]));

        handleInput(events[i]);
    }

    // -----------------------------------------------------
    // 6. Zustand sichern und schlafen
    // -----------------------------------------------------

    diagStep("save + Deep Sleep");
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

    diagStep("Display::begin()");
    _display.begin();
    diagStep("Display::begin() fertig");

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

    diagStep("Display::show()");
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

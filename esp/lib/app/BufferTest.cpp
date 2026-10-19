#include "BufferTest.h"

#include <Arduino.h>
#include <Wire.h>

#include "ASCII16Seg.h"
#include "HT16K33.h"
#include "I2CMasterControl.h"
#include "DebugLogger.h"
#include "pinMapping.h"

namespace
{
    constexpr unsigned long PERIOD_MS = 1000;

    // Zusammenfassung alle N Runden
    constexpr uint16_t SUMMARY_EVERY = 10;

    // Gleiche Reihenfolge wie in Display.cpp
    constexpr uint8_t MODULES[] =
    {
        0x70, 0x71, 0x72,
        0x73, 0x74, 0x75,
        0x76, 0x77, 0x7F,   // 0x7F: hinter LTC4316 A
        0x79, 0x7B, 0x7D    // hinter LTC4316 B
    };

    constexpr uint8_t MODULE_COUNT = sizeof(MODULES) / sizeof(MODULES[0]);
    constexpr uint8_t RAM_SIZE = HT16K33::BUFFER_SIZE;

    // Endstand pro Modul seit dem Start
    struct Stats
    {
        uint32_t ok;
        uint32_t cmdNack;    // 0x81 nicht quittiert
        uint32_t writeFail;  // Text-Schreibzugriff abgebrochen
        uint32_t readFail;   // Zuruecklesen gescheitert
        uint32_t mismatch;   // Text kam falsch an
        uint32_t busError;   // Code 4 oder SDA hing
    };

    Stats stats[MODULE_COUNT];

    uint8_t sendCommand(uint8_t address, uint8_t command)
    {
        Wire.beginTransmission(address);
        Wire.write(command);
        return Wire.endTransmission();
    }

    void buildText(uint8_t* ram, const char* text)
    {
        for (uint8_t i = 0; i < HT16K33::CHARS_PER_MODULE; i++)
        {
            const char c = (text[i] != '\0') ? text[i] : ' ';
            const uint16_t seg = ASCII16Seg::get(c);
            ram[i * 2]     = seg & 0xFF;
            ram[i * 2 + 1] = seg >> 8;
        }
    }

    uint8_t writeRam(uint8_t address, const uint8_t* ram)
    {
        Wire.beginTransmission(address);
        Wire.write((uint8_t)0x00);
        Wire.write(ram, RAM_SIZE);
        return Wire.endTransmission();
    }

    // 0 = ok, 1 = Lesen gescheitert, 2 = Inhalt falsch
    uint8_t verifyRam(uint8_t address, const uint8_t* expected)
    {
        Wire.beginTransmission(address);
        Wire.write((uint8_t)0x00);
        if (Wire.endTransmission() != 0)
            return 1;

        if (Wire.requestFrom(address, RAM_SIZE) != RAM_SIZE)
            return 1;

        bool equal = true;
        for (uint8_t i = 0; i < RAM_SIZE; i++)
            if (Wire.read() != expected[i])
                equal = false;

        return equal ? 0 : 2;
    }

    bool releaseBusIfStuck()
    {
        if (digitalRead(Pins::I2C_SDA) == HIGH)
            return false;

        I2CMasterControl::recoverBus();
        return true;
    }

    // Ergebnis eines Moduls in dieser Runde
    enum class Result { Missing, Ok, CmdNack, WriteFail, ReadFail, Mismatch, BusError };

    const char* resultName(Result r)
    {
        switch (r)
        {
            case Result::Ok:        return "ok";
            case Result::CmdNack:   return "FEHLER 0x81 NACK";
            case Result::WriteFail: return "FEHLER Text abgebrochen";
            case Result::ReadFail:  return "FEHLER Lesen";
            case Result::Mismatch:  return "FEHLER Text falsch";
            case Result::BusError:  return "FEHLER Bus";
            default:                return "fehlt";
        }
    }

    Result writeModule(uint8_t index, uint32_t round)
    {
        const uint8_t address = MODULES[index];

        // Oszillator ein - zugleich der Anwesenheitstest.
        // Code 2 = niemand quittiert die Adresse: nicht angeschlossen.
        uint8_t code = sendCommand(address, 0x21);
        if (code == 2) return Result::Missing;
        if (code == 4) return Result::BusError;

        char text[9];
        snprintf(text, sizeof(text), "ADR %02X %lu", address, (unsigned long)(round % 10));

        uint8_t ram[RAM_SIZE];
        buildText(ram, text);

        // Erst den Text, dann einschalten - wie im Normalbetrieb
        code = writeRam(address, ram);
        if (code == 4) return Result::BusError;
        const bool writeOk = (code == 0);

        code = sendCommand(address, 0x81);                         // Anzeige ein, Bit 0 = 1
        if (code == 4) return Result::BusError;
        const bool cmdOk = (code == 0);

        sendCommand(address, 0xE0 | HT16K33::DEFAULT_BRIGHTNESS);  // Helligkeit

        const uint8_t verify = verifyRam(address, ram);

        if (!cmdOk)        return Result::CmdNack;
        if (!writeOk)      return Result::WriteFail;
        if (verify == 1)   return Result::ReadFail;
        if (verify == 2)   return Result::Mismatch;
        return Result::Ok;
    }

    void count(Stats& s, Result r)
    {
        switch (r)
        {
            case Result::Ok:        s.ok++;        break;
            case Result::CmdNack:   s.cmdNack++;   break;
            case Result::WriteFail: s.writeFail++; break;
            case Result::ReadFail:  s.readFail++;  break;
            case Result::Mismatch:  s.mismatch++;  break;
            case Result::BusError:  s.busError++;  break;
            default: break;
        }
    }

    void printSummary(uint32_t round)
    {
        DebugSerial.printf("[BUF] ---- Stand nach %lu Runden ----\n", (unsigned long)round);

        bool any = false;
        for (uint8_t i = 0; i < MODULE_COUNT; i++)
        {
            const Stats& s = stats[i];
            const uint32_t errors = s.cmdNack + s.writeFail + s.readFail + s.mismatch + s.busError;

            if (s.ok + errors == 0)
                continue;   // nie angeschlossen

            any = true;
            DebugSerial.printf("[BUF]   0x%02X: %lu ok, %lu Fehler (0x81 NACK %lu, Text abgebrochen %lu, Lesen %lu, Text falsch %lu, Bus %lu)\n",
                               MODULES[i], (unsigned long)s.ok, (unsigned long)errors,
                               (unsigned long)s.cmdNack, (unsigned long)s.writeFail,
                               (unsigned long)s.readFail, (unsigned long)s.mismatch,
                               (unsigned long)s.busError);
        }

        if (!any)
            DebugSerial.println("[BUF]   bisher hat kein Modul geantwortet");

        Serial.flush();
    }
}

[[noreturn]] void BufferTest::run()
{
    DebugSerial.println("\n[BUF] ======== Buffer-Test: ganzer Bildschirm zeigt 'ADR <Adresse> <Zaehler>' ========");
    DebugSerial.printf("[BUF] Takt %lu Hz, neue Runde alle %lu ms\n",
                       (unsigned long)I2CMasterControl::I2C_CLOCK_HZ, PERIOD_MS);

    // Bus fuer den ganzen Test beim ESP
    I2CMasterControl::enable();

    DebugSerial.printf("[BUF] Ruhepegel SDA=%d SCL=%d (beide 1 erwartet)\n",
                       digitalRead(Pins::I2C_SDA), digitalRead(Pins::I2C_SCL));

    memset(stats, 0, sizeof(stats));

    for (uint32_t round = 1; ; round++)
    {
        char line[160];
        size_t offset = snprintf(line, sizeof(line), "[BUF] #%lu", (unsigned long)round);
        uint8_t present = 0;

        for (uint8_t i = 0; i < MODULE_COUNT; i++)
        {
            Result r = writeModule(i, round);

            if (releaseBusIfStuck() && r == Result::Ok)
                r = Result::BusError;

            count(stats[i], r);

            if (r != Result::Missing)
            {
                present++;
                if (offset < sizeof(line))
                    offset += snprintf(line + offset, sizeof(line) - offset,
                                       "  0x%02X %s", MODULES[i], resultName(r));
            }

            yield();
        }

        if (present == 0)
            DebugSerial.printf("%s  kein Modul antwortet\n", line);
        else
            DebugSerial.println(line);

        if (round % SUMMARY_EVERY == 0)
            printSummary(round);

        Serial.flush();
        delay(PERIOD_MS);
    }
}

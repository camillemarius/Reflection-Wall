#pragma once

#include <Arduino.h>

#include "PiSession.h"
#include "Clock.h"
#include "NightData.h"

// ---------------------------------------------------------
// Zustand, der einen Reset ueberlebt
// ---------------------------------------------------------
// Der ESP schlaeft zwischen zwei Weckvorgaengen im Deep Sleep
// und wird vom INT-Ausgang des GPIO Expanders ueber RST
// geweckt. Jeder Weckvorgang ist ein vollstaendiger Neustart:
// RAM, Objektzustand und millis() fangen bei null an.
//
// Was den Neustart ueberdauern muss, liegt deshalb im
// RTC-Speicher. Der behaelt seinen Inhalt sowohl ueber den
// Deep Sleep als auch ueber einen externen Reset - nur ein
// echter Spannungsausfall loescht ihn. Magic und CRC
// unterscheiden gueltige Daten von dem Muell, der nach dem
// Einschalten dort steht.

// Zustand der Anzeige. Die Zahlenwerte stehen im RTC-Speicher und
// duerfen sich nicht aendern (sonst stimmt MAGIC nicht mehr).
enum class DisplayState : uint8_t
{
    Off     = 0,  // aus
    On      = 1,  // an
    Writing = 2   // wird geschrieben (der Durchlauf brach dabei ab)
};

class PersistentState
{
public:
    struct Data
    {
        // Registerwert des Expanders beim letzten Aufwachen.
        // Referenz fuer die Flankenauswertung.
        uint16_t lastExpanderState;

        // Zustand der Anzeige
        DisplayState displayState;

        // 1 = die BT1-Minute laeuft
        uint8_t  button1Active;

        // Nur fuer die Diagnose: Anzahl Weckvorgaenge seit
        // dem letzten Einschalten
        uint32_t wakeCount;

        // Welches Zitat gerade steht: Position in der Liste und
        // Datum "JJJJ-MM-TT" ("" fuer einen Eintrag ohne Datum).
        // Das Datum findet den Eintrag wieder, wenn die Liste
        // sich verschoben hat.
        uint8_t  shownIndex;
        char     shownDate[11];

        // Sitzung mit dem Pi (PiSession). Ein Reset durch eine
        // Taste oder den Radar macht im selben Zustand weiter.
        SessionData session;

        // 1 = der ESP hat den Pi zuletzt eingeschaltet. Das
        // Flipflop laesst sich nicht zuruecklesen (F5).
        uint8_t  piPowered;

        // Nummern der Verbindung (PiLink::state): naechste eigene
        // Nummer, letzte Nummer des Pi und ob die gilt (0/1)
        uint8_t  txSeq;
        uint8_t  rxSeq;
        uint8_t  rxValid;

        // Uhr (UTC) und Auftrag der Nacht
        ClockData clock;
        NightData night;
    };

    // Liest den Zustand. Rueckgabe false bedeutet Kaltstart
    // (Spannung war weg oder Daten defekt); data enthaelt dann
    // die Startwerte.
    static bool load(Data& data);

    static void save(const Data& data);

private:
    struct Block
    {
        uint32_t magic;
        uint32_t crc;
        Data     data;
    };

    // "RWL4" - aendert sich, sobald sich das Layout von Data
    // aendert, damit alte Daten nach einem Update verworfen
    // statt fehlinterpretiert werden.
    static constexpr uint32_t MAGIC = 0x52574C34;

    // Offset im RTC-Speicher, gezaehlt in 4-Byte-Bloecken
    static constexpr uint32_t RTC_OFFSET = 0;

    static void setDefaults(Data& data);
    static uint32_t crc32(const uint8_t* data, size_t length);
};

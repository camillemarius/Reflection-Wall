#pragma once

// Regeln der Wand: was beim Aufwachen gezeigt wird und wann sie ausgeht.
// Reine Logik ohne Arduino-Abhaengigkeit.
enum class WallAction
{
    None,
    ShowNewest,
    ShowNext,
    ShowCurrent
};

struct WallBoot
{
    bool displayOn;      // Anzeige war beim letzten Durchlauf an
    bool displayWriting; // letzter Durchlauf brach beim Schreiben ab
    bool radarHigh;      // INT_HLK jetzt HIGH
    bool button1;        // BT1-Ereignis in diesem Durchlauf
};

constexpr unsigned long BUTTON1_ON_MS = 60000;

WallAction decideOnBoot(const WallBoot& boot);
bool wallShouldTurnOff(bool radarHigh, bool button1Active, unsigned long msSinceBoot);

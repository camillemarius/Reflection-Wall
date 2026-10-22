#pragma once

#include <cstddef>
#include <string>

#include "QuoteList.h"

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

// Welcher Eintrag der Liste angezeigt wird. shownIndex/shownDate sind der
// zuletzt gespeicherte Stand; das Datum findet den Eintrag nach einer
// Verschiebung der Liste wieder.
std::size_t selectIndex(const QuoteList& list, WallAction action,
                        std::size_t shownIndex, const std::string& shownDate);

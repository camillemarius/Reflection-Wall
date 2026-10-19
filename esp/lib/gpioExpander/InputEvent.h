#pragma once

enum class InputEvent
{
    NONE,

    BT1,
    BT2,
    BT3,
    BT4,
    BT5,
    BT6,

    UNKNOWN
};

// Wann ein Taster eine Aktion ausloest.
// Die Angaben beziehen sich auf den elektrischen Pegel am
// Expander-Pin, nicht auf "gedrueckt": die Taster sind aktiv
// LOW, ein Druck ist also eine negative Flanke.
enum class InputTrigger
{
    NONE,           // Taster ausgewertet, loest nichts aus
    RISING_EDGE,    // LOW -> HIGH  (Taster losgelassen)
    FALLING_EDGE,   // HIGH -> LOW  (Taster gedrueckt)
    LEVEL_HIGH,     // solange HIGH (Taster offen)
    LEVEL_LOW,      // solange LOW  (Taster gehalten)
    ANY_EDGE        // jeder Wechsel: fuer Taster hinter einem
                    // Toggle-Flipflop, das bei jedem Druck kippt
};

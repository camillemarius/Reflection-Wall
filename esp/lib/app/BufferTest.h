#pragma once

// ---------------------------------------------------------
// Test fuer den I2C-Buffer (PCA9517A)
// ---------------------------------------------------------
// Beschreibt endlos den ganzen Bildschirm: jedes der 12 Module
// zeigt "ADR <Adresse> <Zaehler>", der Zaehler springt jede
// Sekunde weiter. Es muessen nicht alle Module angeschlossen
// sein - wer nicht antwortet, wird als "fehlt" uebersprungen.
//
// Pro angeschlossenem Modul wird geprueft:
//   - Befehl 0x81 (Bit 0 = 1, der Fall, der hinter den LTC4316
//     scheiterte) wird quittiert
//   - der Text kommt vollstaendig an (RAM zuruecklesen)
//
// Kehrt nicht zurueck.

namespace BufferTest
{
    [[noreturn]] void run();
}

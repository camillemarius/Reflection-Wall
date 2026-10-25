#pragma once
#include "PiLink.h"

// BT3 ausserhalb einer Sitzung (Annahme 13, Teil 4 Tabelle 5.2): schickt
// PING, beantwortet Anfragen des Pi und loggt das Ergebnis. Laeuft
// mindestens durationMs, und bis keine eigene Anfrage mehr offen ist.
void runLinkTest(PiLink& link, unsigned long durationMs);

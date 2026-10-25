#pragma once
#include "PiLink.h"

// BT3 ohne Sitzung, bis Teil 2 (Annahme 13): schickt PING, beantwortet
// Anfragen des Pi und loggt das Ergebnis. Laeuft mindestens durationMs,
// und bis keine eigene Anfrage mehr offen ist.
void runLinkTest(PiLink& link, unsigned long durationMs);

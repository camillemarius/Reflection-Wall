#include <Arduino.h>

#include "application.h"

// ---------------------------------------------------------
// Reflection Wall
// ---------------------------------------------------------
// Der ESP haelt keine Hauptschleife mehr. Er liegt im Deep
// Sleep, bis der GPIO Expander ueber seinen INT-Ausgang einen
// Reset ausloest (ebenso der Radar) - dann laeuft setup() einmal
// durch, wertet Taster und Radar aus und legt sich wieder hin.
// Ist die Wand an, bleibt setup() wach, bis die Regeln das
// Abschalten verlangen.

Application application;

void setup()
{
    // Kehrt nicht zurueck: run() endet im Deep Sleep.
    application.run();
}

void loop()
{
    // Wird nie erreicht. Falls der Deep Sleep doch einmal
    // fehlschlaegt, ist ein Neustart das Richtige - Warten in
    // der Schleife waere genau das Verhalten, das hier nicht
    // mehr vorgesehen ist.
    ESP.restart();
}

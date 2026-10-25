#include "PiPower.h"

constexpr unsigned long PiPower::PULSE_MS;

PiPower::PiPower(IPowerPin& pin)
    : _pin(pin), _on(false)
{
}

// Der Ruhepegel wird gemessen statt angenommen: uebernimmt der Pin
// beim Wechsel auf Ausgang exakt den Pegel, den die Leitung ohnehin
// fuehrt, entsteht keine Flanke und das Relais bleibt unberuehrt
// (das erste drive() nach readIdle() ist derselbe Pegel).
//
// Den resultierenden Relaiszustand liest der ESP nicht zurueck - er
// liegt im Flipflop und ueberlebt auch dessen Stromausfall.
//
// Aufgerufen wird das nur, wenn tatsaechlich geschaltet werden soll.
// In jedem anderen Durchlauf bleibt GPIO12 Eingang und damit
// hochohmig: der ESP haengt sich nicht bei jedem Boot an die
// Taktleitung des Flipflops.
void PiPower::toggle()
{
    const bool idle = _pin.readIdle();

    _pin.drive(idle);
    _pin.drive(!idle);
    _pin.waitMs(PULSE_MS);
    _pin.drive(idle);

    _on = !_on;
}

bool PiPower::switchTo(bool on)
{
    if (on == _on)
        return false;

    toggle();
    return true;
}

bool PiPower::isOn() const
{
    return _on;
}

void PiPower::restore(bool on)
{
    _on = on;
}

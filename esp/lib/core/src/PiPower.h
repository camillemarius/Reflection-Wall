#pragma once

// ---------------------------------------------------------
// Pi-Speisung
// ---------------------------------------------------------
// GPIO12 taktet ein Flipflop, das den Relaiszustand auch ohne
// den ESP haelt. Ein ESP-Reset aendert ihn nicht, und der ESP
// kann ihn nicht zuruecklesen (F5). PiPower merkt sich deshalb
// nur, was der ESP zuletzt geschaltet hat.

// Der Pin zum Flipflop. Hinter dieser Schnittstelle steckt auf
// dem ESP PowerSwitchPin, im PC-Test RecordingPin.
class IPowerPin
{
public:
    virtual ~IPowerPin() = default;

    virtual bool readIdle() = 0;           // Pin als Eingang, Pegel lesen
    virtual void drive(bool high) = 0;     // Pegel setzen, Pin ist danach Ausgang
    virtual void waitMs(unsigned long ms) = 0;
};

class PiPower
{
public:
    // Breite des Clock-Pulses fuer das Flipflop am Relais
    static constexpr unsigned long PULSE_MS = 50;

    explicit PiPower(IPowerPin& pin);

    // Ein Puls gegen den gemessenen Ruhepegel kippt das Flipflop
    // und damit isOn().
    void toggle();

    // Pulst nur, wenn isOn() != on. true, wenn gepulst wurde.
    bool switchTo(bool on);

    // Was der ESP zuletzt geschaltet hat; anfangs false.
    bool isOn() const;

    // Setzt den Wert aus dem RTC-Speicher, ohne Puls.
    void restore(bool on);

private:
    IPowerPin& _pin;
    bool _on;
};

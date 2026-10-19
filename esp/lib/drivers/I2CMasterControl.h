#pragma once

#include <Arduino.h>

class I2CMasterControl
{
public:

    /**
     * I2C Taktrate in Hz.
     * Standard waere 100000; bewusst reduziert, weil der Bus sonst
     * mit den langen Leitungen / dem Analog Switch Fehler zeigt.
     */
    static constexpr uint32_t I2C_CLOCK_HZ = 10000;

    /**
     * Einschwingzeit des Analog Switch nach dem Umschalten.
     * Der Schalter selbst ist nach <1us durch; die Zeit deckt
     * vor allem das Umladen der Busleitungen ueber die Pull-Ups
     * und einen eventuell noch nachlaufenden Zugriff des
     * anderen Masters ab.
     */
    static constexpr uint32_t SETTLE_US = 100;

    /**
     * Maximale Wartezeit, bis der Bus nach dem Umschalten
     * wirklich idle ist (SDA und SCL beide HIGH).
     */
    static constexpr uint32_t BUS_IDLE_TIMEOUT_US = 10000;

    static void begin();

    /**
     * Scannt den Bus ab und meldet neben den gefundenen
     * Adressen auch die Ruhepegel und die Fehlercodes.
     *
     * @param passes Anzahl Durchlaeufe. Mehr als einer zeigt,
     *               ob der erste Zugriff nach dem Umschalten
     *               systematisch scheitert.
     */
    static void scan(Print& output, uint8_t passes = 2);

    /**
     * Schaltet den ESP8266 als I2C Master ein
     */
    static void enable();


    /**
     * Gibt den I2C Bus wieder frei
     */
    static void disable();

    /**
     * Wartet, bis SDA und SCL beide HIGH sind.
     * @return false bei Timeout - der Bus haengt dann fest.
     */
    static bool waitForIdleBus();

    /**
     * Befreit einen Bus, auf dem ein Teilnehmer SDA festhaelt
     * (9 SCL-Pulse + STOP). Wird von enable() automatisch
     * aufgerufen, wenn SDA nach dem Umschalten LOW ist.
     * @return true, wenn SDA danach wieder HIGH ist
     */
    static bool recoverBus();

    /**
     * Anzahl erfolgreicher Bus-Befreiungen seit dem Start
     */
    static uint8_t recoveryCount();

private:

    static uint8_t _recoveries;
};
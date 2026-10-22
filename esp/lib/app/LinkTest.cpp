#include "LinkTest.h"
#include "DebugLogger.h"

#include <Arduino.h>

namespace
{
    // PiLink loggt selbst nicht: jede verworfene Zeile meldet die Firmware hier.
    void logDiscarded(const PiLink& link, unsigned long& logged)
    {
        if (link.discarded() > logged)
        {
            logged = link.discarded();
            DebugSerial.printf("[LINK] Zeile verworfen (%lu insgesamt): %s\n",
                               logged, LinkCodec::errorName(link.lastError()));
        }
    }
}

void runLinkTest(PiLink& link, unsigned long durationMs)
{
    const unsigned long start = millis();
    unsigned long logged = link.discarded();

    if (link.send("PING", "", start))
        DebugSerial.printf("[LINK] Verbindungstest: PING #%02X\n", (unsigned)(link.state().txSeq - 1) & 0xFF);
    else
        DebugSerial.println("[LINK] PING nicht gesendet (Anfrage offen)");

    while (true)
    {
        const unsigned long now = millis();
        const LinkEvent ev = link.poll(now);
        logDiscarded(link, logged);

        switch (ev.kind)
        {
            case LinkEvent::Kind::Response:
                DebugSerial.printf("[LINK] PING -> %s nach %lu ms\n",
                                   ev.message.command.c_str(), now - start);
                break;
            case LinkEvent::Kind::Expired:
                DebugSerial.printf("[LINK] keine Antwort auf PING nach %lu ms\n", now - start);
                break;
            case LinkEvent::Kind::Request:
                link.reply("OK");
                DebugSerial.printf("[LINK] Anfrage #%02X %s -> OK\n",
                                   (unsigned)ev.message.seq, ev.message.command.c_str());
                break;
            default:
                break;
        }

        if (now - start >= durationMs && !link.busy())
            break;

        yield();
    }

    if (link.discarded() > 0)
        DebugSerial.printf("[LINK] %lu Zeilen verworfen, zuletzt %s\n",
                           link.discarded(), LinkCodec::errorName(link.lastError()));
}

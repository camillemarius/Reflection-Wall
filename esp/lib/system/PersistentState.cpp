#include "PersistentState.h"
#include "QuoteList.h"

// Das Datum steckt samt abschliessender Null in shownDate. Waere es kuerzer als
// ein Datum der Zitatliste, kuerzte strncpy es still und die Wand faende das
// gezeigte Zitat nicht mehr.
static_assert(sizeof(PersistentState::Data::shownDate) >= QuoteList::MAX_DATE_LENGTH + 1,
              "shownDate fasst das laengste Datum der Zitatliste nicht");

// Das Byte im RTC-Speicher bleibt ein Byte (MAGIC aendert sich nicht).
static_assert(sizeof(DisplayState) == 1, "DisplayState muss ein Byte bleiben");

static_assert(sizeof(PersistentState::Data) % 4 == 0,
              "RTC-Speicher wird in 4-Byte-Bloecken gelesen und geschrieben");

// 20 Byte Wand, 28 Byte Sitzung, 4 Byte Speisung und Nummern. Aendert sich
// die Groesse, muss auch MAGIC sich aendern.
static_assert(sizeof(PersistentState::Data) == 52, "Layout von Data geaendert: MAGIC anpassen");


void PersistentState::setDefaults(Data& data)
{
    // 0xFFFF = kein Taster gedrueckt. Der Wert wird beim
    // Kaltstart ohnehin durch den tatsaechlich gelesenen
    // Registerwert ersetzt, bevor Flanken ausgewertet werden.
    data.lastExpanderState = 0xFFFF;
    data.displayState = DisplayState::Off;
    data.button1Active = 0;
    data.wakeCount = 0;
    data.shownIndex = 0;
    memset(data.shownDate, 0, sizeof(data.shownDate));

    // Nach einem Kaltstart ist auch das Flipflop zurueckgesetzt,
    // der Pi also aus (Spec 7).
    PiSession::reset(data.session);
    data.piPowered = 0;
    data.txSeq = 0;
    data.rxSeq = 0;
    data.rxValid = 0;
}


bool PersistentState::load(Data& data)
{
    Block block;

    const bool read = ESP.rtcUserMemoryRead(RTC_OFFSET,
                                            reinterpret_cast<uint32_t*>(&block),
                                            sizeof(block));

    if (!read || block.magic != MAGIC)
    {
        setDefaults(data);
        return false;
    }

    const uint32_t crc = crc32(reinterpret_cast<const uint8_t*>(&block.data),
                               sizeof(block.data));

    if (crc != block.crc)
    {
        setDefaults(data);
        return false;
    }

    data = block.data;

    return true;
}


void PersistentState::save(const Data& data)
{
    Block block;

    block.magic = MAGIC;
    block.data  = data;
    block.crc   = crc32(reinterpret_cast<const uint8_t*>(&block.data),
                        sizeof(block.data));

    ESP.rtcUserMemoryWrite(RTC_OFFSET,
                           reinterpret_cast<uint32_t*>(&block),
                           sizeof(block));
}


// Standard-CRC32 (Polynom 0xEDB88320), bitweise gerechnet.
// Bei 52 Byte Nutzdaten lohnt keine Tabelle.

uint32_t PersistentState::crc32(const uint8_t* data, size_t length)
{
    uint32_t crc = 0xFFFFFFFF;

    while (length--)
    {
        crc ^= *data++;

        for (uint8_t bit = 0; bit < 8; bit++)
            crc = (crc & 1) ? (crc >> 1) ^ 0xEDB88320 : (crc >> 1);
    }

    return ~crc;
}

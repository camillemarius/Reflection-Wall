#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

// Ein Speicher mit 16-Bit-Adressen; auf dem Geraet der FRAM am I2C-Bus
class IByteStore
{
public:
    virtual ~IByteStore() = default;
    virtual bool read(uint16_t address, uint8_t* out, std::size_t length) = 0;
    virtual bool write(uint16_t address, const uint8_t* data, std::size_t length) = 0;
};

namespace SlotLayout
{
    constexpr uint16_t SLOT_A = 0x0000;
    constexpr uint16_t SLOT_B = 0x1000;
    constexpr std::size_t SLOT_SIZE = 4096;
    constexpr std::size_t HEADER_SIZE = 16;
    constexpr std::size_t MAX_CONTENT = SLOT_SIZE - HEADER_SIZE;   // 4080
    constexpr uint32_t MAGIC = 0x31515752;                          // "RWQ1"
}

// Zwei Plaetze im Wechsel: Erst die Liste, dann der Kopf. Ein Reset mitten im Schreiben
// laesst den anderen Platz unberuehrt und gueltig.
class SlotStore
{
public:
    enum class ReadResult { Ok, Empty, BusError };

    explicit SlotStore(IByteStore& bytes);
    ReadResult read(std::string& content);       // Inhalt des massgeblichen Platzes
    bool write(const std::string& content);      // false: zu lang oder Busfehler

private:
    static constexpr int NO_SLOT = -1;

    uint16_t slotAddress(int slot) const;

    IByteStore& bytes_;
    bool known_ = false;     // Stand schon gelesen oder selbst geschrieben
    int slot_ = NO_SLOT;     // 0 = A, 1 = B, NO_SLOT = keiner gueltig
    uint32_t number_ = 0;    // laufende Nummer des massgeblichen Platzes
};

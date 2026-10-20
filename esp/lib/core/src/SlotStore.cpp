#include "SlotStore.h"
#include "Crc32.h"

namespace
{
    uint32_t getU32(const uint8_t* p)
    {
        return static_cast<uint32_t>(p[0]) | (static_cast<uint32_t>(p[1]) << 8) |
               (static_cast<uint32_t>(p[2]) << 16) | (static_cast<uint32_t>(p[3]) << 24);
    }

    void putU32(uint8_t* p, uint32_t v)
    {
        p[0] = static_cast<uint8_t>(v);
        p[1] = static_cast<uint8_t>(v >> 8);
        p[2] = static_cast<uint8_t>(v >> 16);
        p[3] = static_cast<uint8_t>(v >> 24);
    }
}

SlotStore::SlotStore(IByteStore& bytes) : bytes_(bytes)
{
}

uint16_t SlotStore::slotAddress(int slot) const
{
    return slot == 0 ? SlotLayout::SLOT_A : SlotLayout::SLOT_B;
}

SlotStore::ReadResult SlotStore::read(std::string& content)
{
    content.clear();
    uint8_t head[2][SlotLayout::HEADER_SIZE];
    for (int s = 0; s < 2; ++s)
    {
        if (!bytes_.read(slotAddress(s), head[s], SlotLayout::HEADER_SIZE))
        {
            return ReadResult::BusError;
        }
    }

    // Kandidaten mit der hoeheren Nummer zuerst
    int order[2] = {0, 1};
    if (getU32(head[1] + 4) > getU32(head[0] + 4))
    {
        order[0] = 1;
        order[1] = 0;
    }

    for (int i = 0; i < 2; ++i)
    {
        const int s = order[i];
        const uint8_t* h = head[s];
        const uint32_t length = getU32(h + 8);
        if (getU32(h) != SlotLayout::MAGIC || length > SlotLayout::MAX_CONTENT)
        {
            continue;
        }
        std::string text(length, '\0');
        if (length > 0 &&
            !bytes_.read(slotAddress(s) + SlotLayout::HEADER_SIZE, reinterpret_cast<uint8_t*>(&text[0]), length))
        {
            return ReadResult::BusError;
        }
        const uint32_t crc = crc32Ieee(reinterpret_cast<const uint8_t*>(text.data()), length, crc32Ieee(h + 4, 8));
        if (crc != getU32(h + 12))
        {
            continue;
        }
        known_ = true;
        slot_ = s;
        number_ = getU32(h + 4);
        content = text;
        return ReadResult::Ok;
    }

    known_ = true;
    slot_ = NO_SLOT;
    number_ = 0;
    return ReadResult::Empty;
}

bool SlotStore::write(const std::string& content)
{
    if (content.size() > SlotLayout::MAX_CONTENT)
    {
        return false;
    }
    if (!known_)
    {
        std::string ignored;
        if (read(ignored) == ReadResult::BusError)
        {
            return false;
        }
    }

    const int target = slot_ == 0 ? 1 : 0;
    const uint32_t number = number_ + 1;
    const uint32_t length = static_cast<uint32_t>(content.size());

    uint8_t head[SlotLayout::HEADER_SIZE];
    putU32(head, SlotLayout::MAGIC);
    putU32(head + 4, number);
    putU32(head + 8, length);
    putU32(head + 12, crc32Ieee(reinterpret_cast<const uint8_t*>(content.data()), length, crc32Ieee(head + 4, 8)));

    // Erst die Liste, dann der Kopf
    if (length > 0 &&
        !bytes_.write(slotAddress(target) + SlotLayout::HEADER_SIZE,
                      reinterpret_cast<const uint8_t*>(content.data()), length))
    {
        known_ = false;
        return false;
    }
    if (!bytes_.write(slotAddress(target), head, SlotLayout::HEADER_SIZE))
    {
        known_ = false;
        return false;
    }
    slot_ = target;
    number_ = number;
    return true;
}

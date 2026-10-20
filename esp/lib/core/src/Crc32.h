#pragma once

#include <cstddef>
#include <cstdint>

// CRC-32 nach IEEE 802.3; crc ist der fertige Wert des vorherigen Stuecks, damit lassen sich Teile aneinanderhaengen
uint32_t crc32Ieee(const uint8_t* data, std::size_t length, uint32_t crc = 0);

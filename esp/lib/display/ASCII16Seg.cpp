#include "ASCII16Seg.h"


uint16_t ASCII16Seg::get(char c)
{
    switch (toupper(c))
    {
        case ' ': return 0x0000;
        case '-': return 0x0101;
        case '.': return 0x0004;
        case '/': return 0x0808;
        case ':': return 0x0808;
        case '+': return 0x1111;
        case '*': return 0x4848;


        case '0': return 0xA6A2;
        case '1': return 0x8002;
        case '2': return 0x2723;
        case '3': return 0xA523;
        case '4': return 0x8183;
        case '5': return 0xA5A1;
        case '6': return 0xA7A1;
        case '7': return 0x8002;
        case '8': return 0xA7A3;
        case '9': return 0xA5A3;


        case 'A': return 0x83A3;
        case 'B': return 0xB433;
        case 'C': return 0x26A0;
        case 'D': return 0xB432;
        case 'E': return 0x27A1;
        case 'F': return 0x03A1;
        case 'G': return 0xA6A1;
        case 'H': return 0x8383;
        case 'I': return 0x3430;
        case 'J': return 0xA622;
        case 'K': return 0x4388;
        case 'L': return 0x2680;
        case 'M': return 0x82CA;
        case 'N': return 0xC2C2;
        case 'O': return 0xA6A2;
        case 'P': return 0x03A3;
        case 'Q': return 0xE6A2;
        case 'R': return 0x43A3;
        case 'S': return 0xA5A1;
        case 'T': return 0x1030;
        case 'U': return 0xA682;
        case 'V': return 0x0A88;
        case 'W': return 0xCA82;
        case 'X': return 0x4848;
        case 'Y': return 0x1183;
        case 'Z': return 0x2C28;

        default:
            return 0x0000;
    }
}
#include "WallLogic.h"

WallAction decideOnBoot(const WallBoot& boot)
{
    if (boot.button1)
    {
        return boot.displayOn ? WallAction::ShowNext : WallAction::ShowNewest;
    }
    if (boot.displayWriting)
    {
        return WallAction::ShowCurrent;
    }
    if (!boot.displayOn && boot.radarHigh)
    {
        return WallAction::ShowNewest;
    }
    return WallAction::None;
}

bool wallShouldTurnOff(bool radarHigh, bool button1Active, unsigned long msSinceBoot)
{
    return !radarHigh && (!button1Active || msSinceBoot >= BUTTON1_ON_MS);
}

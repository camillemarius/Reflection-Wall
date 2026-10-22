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

std::size_t selectIndex(const QuoteList& list, WallAction action,
                        std::size_t shownIndex, const std::string& shownDate)
{
    if (list.empty())
    {
        return 0;
    }
    switch (action)
    {
        case WallAction::ShowNewest:
            return 0;
        case WallAction::ShowNext:
            return list.nextIndex(list.resolveIndex(shownIndex, shownDate));
        default:
            return list.resolveIndex(shownIndex, shownDate);
    }
}

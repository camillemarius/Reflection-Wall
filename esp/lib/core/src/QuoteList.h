#pragma once

#include <cstddef>
#include <string>
#include <vector>

struct Quote
{
    std::string date;
    std::string text;
};

// Liste der letzten Zitate, neuestes zuerst. Reine Logik ohne Arduino-Abhaengigkeit.
class QuoteList
{
public:
    static constexpr std::size_t MAX_QUOTES = 30;

    // Laenge von "JJJJ-MM-TT"; PersistentState::shownDate muss mindestens
    // so viel plus die abschliessende Null fassen (static_assert dort)
    static constexpr std::size_t MAX_DATE_LENGTH = 10;

    static QuoteList parse(const std::string& content);
    std::string serialize() const;

    void addNewest(const std::string& date, const std::string& text);

    std::size_t size() const;
    bool empty() const;
    // index muss gueltig sein; Aufrufer pruefen vorher empty()
    const Quote& at(std::size_t index) const;

    // Findet die Position eines zuvor angezeigten Eintrags wieder, auch nach addNewest()
    std::size_t resolveIndex(std::size_t index, const std::string& date) const;
    std::size_t nextIndex(std::size_t index) const;

private:
    std::vector<Quote> quotes_;
};

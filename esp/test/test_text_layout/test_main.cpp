#include <unity.h>
#include <cstdlib>
#include <string>
#include <vector>
#include "TextLayout.h"
#include "Glyphs.h"
#include "../support/VectorFile.h"

void setUp() {}
void tearDown() {}

static std::vector<Vector> loadAll()
{
    std::vector<Vector> v;
    std::string err;
    bool ok = loadVectors(DISPLAY_VECTORS, v, err);
    TEST_ASSERT_TRUE_MESSAGE(ok, err.c_str());
    TEST_ASSERT_TRUE(v.size() >= 60);
    return v;
}

void test_wrap_vectors()
{
    int count = 0;
    for (const Vector& v : loadAll())
    {
        if (v.str("kind") != "wrap") continue;
        ++count;
        const std::string name = v.str("name");
        TextLayout::Layout l = TextLayout::wrap(v.str("text"));
        TEST_ASSERT_TRUE_MESSAGE(l.rows[0] == v.str("row1"), name.c_str());
        TEST_ASSERT_TRUE_MESSAGE(l.rows[1] == v.str("row2"), name.c_str());
        TEST_ASSERT_TRUE_MESSAGE(l.rows[2] == v.str("row3"), name.c_str());
        TEST_ASSERT_TRUE_MESSAGE(l.rows[3] == v.str("row4"), name.c_str());
        TEST_ASSERT_TRUE_MESSAGE(l.fits == (v.num("fits") == 1), name.c_str());
    }
    TEST_ASSERT_TRUE(count >= 14);
}

void test_glyph_vectors()
{
    int count = 0;
    for (const Vector& v : loadAll())
    {
        if (v.str("kind") != "glyph") continue;
        ++count;
        const std::string name = v.str("name");
        const char c = v.str("char")[0];
        const unsigned long want = std::strtoul(v.str("segments").c_str(), nullptr, 16);
        TEST_ASSERT_EQUAL_UINT_MESSAGE(want, Glyphs::segments(c), name.c_str());
        TEST_ASSERT_EQUAL_INT_MESSAGE(v.num("displayable") == 1, Glyphs::displayable(c), name.c_str());
    }
    TEST_ASSERT_TRUE(count >= 45);
}

void test_seven_differs_from_one()
{
    TEST_ASSERT_NOT_EQUAL(Glyphs::segments('1'), Glyphs::segments('7'));
}

int main(int, char**)
{
    UNITY_BEGIN();
    RUN_TEST(test_wrap_vectors);
    RUN_TEST(test_glyph_vectors);
    RUN_TEST(test_seven_differs_from_one);
    return UNITY_END();
}

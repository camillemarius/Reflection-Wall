#include <unity.h>
#include <string>
#include <vector>
#include "QuoteCheck.h"
#include "../support/VectorFile.h"

void setUp() {}
void tearDown() {}

void test_check_vectors()
{
    std::vector<Vector> all;
    std::string err;
    bool ok = loadVectors(QUOTE_VECTORS, all, err);
    TEST_ASSERT_TRUE_MESSAGE(ok, err.c_str());

    int count = 0;
    for (const Vector& v : all)
    {
        if (v.str("kind") != "check") continue;
        ++count;
        const std::string name = v.str("name");
        TEST_ASSERT_TRUE_MESSAGE(QuoteCheck::acceptable(v.str("text")) == (v.num("acceptable") == 1), name.c_str());
    }
    TEST_ASSERT_TRUE(count >= 15);
}

int main(int, char**)
{
    UNITY_BEGIN();
    RUN_TEST(test_check_vectors);
    return UNITY_END();
}

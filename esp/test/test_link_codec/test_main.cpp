#include <unity.h>
#include <string>
#include <vector>
#include "LinkCodec.h"
#include "../support/VectorFile.h"

void setUp() {}
void tearDown() {}

static std::vector<Vector> loadAll()
{
    std::vector<Vector> v;
    std::string err;
    bool ok = loadVectors(PROTOCOL_VECTORS, v, err);
    TEST_ASSERT_TRUE_MESSAGE(ok, err.c_str());
    return v;
}

static LinkCodec::Message messageOf(const Vector& v)
{
    LinkCodec::Message m;
    m.seq = static_cast<uint8_t>(v.num("seq"));
    m.command = v.str("command");
    m.data = v.str("data");
    return m;
}

static void expectDecoded(const Vector& v)
{
    const std::string name = v.str("name");
    LinkCodec::Message m;
    TEST_ASSERT_EQUAL_STRING_MESSAGE("NONE", LinkCodec::errorName(LinkCodec::decode(v.str("line"), m)), name.c_str());
    TEST_ASSERT_EQUAL_INT_MESSAGE(v.num("seq"), m.seq, name.c_str());
    TEST_ASSERT_TRUE_MESSAGE(v.str("command") == m.command, name.c_str());
    TEST_ASSERT_TRUE_MESSAGE(v.str("data") == m.data, name.c_str());
}

void test_vector_file_is_read()
{
    std::vector<Vector> v = loadAll();
    TEST_ASSERT_TRUE(v.size() >= 60);
    bool seenBackslash = false, seenGarbage = false;
    for (const Vector& x : v)
    {
        if (x.str("name") == "escape_backslash")
        {
            seenBackslash = true;
            TEST_ASSERT_TRUE(x.str("line") == "$02:QUOTE|A\\\\B*1D");
        }
        if (x.str("name") == "garbage_before_start")
        {
            seenGarbage = true;
            std::string l = x.str("line");
            TEST_ASSERT_EQUAL_UINT(13, l.size());
            TEST_ASSERT_EQUAL_UINT8(0, static_cast<uint8_t>(l[0]));
            TEST_ASSERT_EQUAL_UINT8(0xFF, static_cast<uint8_t>(l[1]));
        }
    }
    TEST_ASSERT_TRUE(seenBackslash);
    TEST_ASSERT_TRUE(seenGarbage);
}

void test_missing_file_reports_path()
{
    std::vector<Vector> v;
    std::string err;
    TEST_ASSERT_FALSE(loadVectors("../tests/gibt_es_nicht.json", v, err));
    TEST_ASSERT_EQUAL_STRING("../tests/gibt_es_nicht.json", err.c_str());
}

void test_both_vectors_encode_and_decode()
{
    int n = 0;
    for (const Vector& v : loadAll())
    {
        if (v.str("kind") != "both") continue;
        ++n;
        const std::string name = v.str("name");
        std::string out;
        TEST_ASSERT_EQUAL_STRING_MESSAGE("NONE", LinkCodec::errorName(LinkCodec::encode(messageOf(v), out)), name.c_str());
        TEST_ASSERT_TRUE_MESSAGE(out == v.str("line"), name.c_str());
        expectDecoded(v);
    }
    TEST_ASSERT_TRUE(n >= 12);
}

void test_decode_vectors()
{
    int n = 0;
    for (const Vector& v : loadAll())
    {
        if (v.str("kind") != "decode") continue;
        ++n;
        expectDecoded(v);
    }
    TEST_ASSERT_EQUAL(3, n);
}

void test_error_vectors()
{
    int n = 0;
    for (const Vector& v : loadAll())
    {
        if (v.str("kind") != "error") continue;
        ++n;
        const std::string name = v.str("name");
        LinkCodec::Message m;
        TEST_ASSERT_EQUAL_STRING_MESSAGE(v.str("error").c_str(), LinkCodec::errorName(LinkCodec::decode(v.str("line"), m)), name.c_str());
    }
    TEST_ASSERT_EQUAL(27, n);
}

void test_encode_error_vectors()
{
    int n = 0;
    for (const Vector& v : loadAll())
    {
        if (v.str("kind") != "encode_error") continue;
        ++n;
        const std::string name = v.str("name");
        std::string out = "x";
        TEST_ASSERT_EQUAL_STRING_MESSAGE(v.str("error").c_str(), LinkCodec::errorName(LinkCodec::encode(messageOf(v), out)), name.c_str());
        TEST_ASSERT_TRUE_MESSAGE(out == "x", name.c_str());
    }
    TEST_ASSERT_EQUAL(4, n);
}

void test_command_vectors()
{
    int n = 0;
    for (const Vector& v : loadAll())
    {
        if (v.str("kind") != "command") continue;
        ++n;
        const std::string name = v.str("name");
        TEST_ASSERT_EQUAL_STRING_MESSAGE(v.str("role").c_str(), LinkCodec::roleName(LinkCodec::roleOf(v.str("command"))), name.c_str());
        if (v.has("deadline_ms"))
        {
            TEST_ASSERT_EQUAL_INT_MESSAGE(v.num("deadline_ms"), static_cast<long>(LinkCodec::deadlineMs(v.str("command"))), name.c_str());
        }
    }
    TEST_ASSERT_EQUAL(13, n);
}

int main(int, char**)
{
    UNITY_BEGIN();
    RUN_TEST(test_vector_file_is_read);
    RUN_TEST(test_missing_file_reports_path);
    RUN_TEST(test_both_vectors_encode_and_decode);
    RUN_TEST(test_decode_vectors);
    RUN_TEST(test_error_vectors);
    RUN_TEST(test_encode_error_vectors);
    RUN_TEST(test_command_vectors);
    return UNITY_END();
}

#include <unity.h>
#include <string>
#include "PiPower.h"
#include "../support/RecordingPin.h"

void setUp() {}
void tearDown() {}

void test_toggle_with_idle_high_pulses_low()
{
    RecordingPin pin;
    pin.idle = true;
    PiPower power(pin);
    power.toggle();
    TEST_ASSERT_EQUAL_STRING("R H L W50 H", pin.log.c_str());
}

void test_toggle_with_idle_low_pulses_high()
{
    RecordingPin pin;
    pin.idle = false;
    PiPower power(pin);
    power.toggle();
    TEST_ASSERT_EQUAL_STRING("R L H W50 L", pin.log.c_str());
}

void test_toggle_flips_is_on()
{
    RecordingPin pin;
    PiPower power(pin);
    TEST_ASSERT_FALSE(power.isOn());
    power.toggle();
    TEST_ASSERT_TRUE(power.isOn());
    power.toggle();
    TEST_ASSERT_FALSE(power.isOn());
}

void test_switch_to_same_state_does_not_pulse()
{
    RecordingPin pin;
    PiPower power(pin);
    TEST_ASSERT_FALSE(power.switchTo(false));
    TEST_ASSERT_EQUAL_STRING("", pin.log.c_str());
}

void test_switch_to_other_state_pulses_once()
{
    RecordingPin pin;
    PiPower power(pin);
    TEST_ASSERT_TRUE(power.switchTo(true));
    TEST_ASSERT_EQUAL_STRING("R H L W50 H", pin.log.c_str());
    TEST_ASSERT_TRUE(power.isOn());
}

void test_restore_sets_state_without_pulse()
{
    RecordingPin pin;
    PiPower power(pin);
    power.restore(true);
    TEST_ASSERT_TRUE(power.isOn());
    TEST_ASSERT_EQUAL_STRING("", pin.log.c_str());
    TEST_ASSERT_TRUE(power.switchTo(false));
    TEST_ASSERT_FALSE(power.isOn());
    TEST_ASSERT_EQUAL_STRING("R H L W50 H", pin.log.c_str());
}

int main(int, char**)
{
    UNITY_BEGIN();
    RUN_TEST(test_toggle_with_idle_high_pulses_low);
    RUN_TEST(test_toggle_with_idle_low_pulses_high);
    RUN_TEST(test_toggle_flips_is_on);
    RUN_TEST(test_switch_to_same_state_does_not_pulse);
    RUN_TEST(test_switch_to_other_state_pulses_once);
    RUN_TEST(test_restore_sets_state_without_pulse);
    return UNITY_END();
}

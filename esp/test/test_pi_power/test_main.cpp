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

// Mindestzeit aus: nur nach einem Ausschalten durch diesen PiPower,
// gemessen ab dem Ende des Pulses
void test_wait_min_off_waits_out_the_rest_after_switch_off()
{
    RecordingPin pin;
    PiPower power(pin, 5000);
    power.restore(true);
    TEST_ASSERT_TRUE(power.switchTo(false));
    pin.now += 1200;
    pin.log.clear();
    TEST_ASSERT_EQUAL_UINT32(3800, power.waitMinOff());
    TEST_ASSERT_EQUAL_STRING("W3800", pin.log.c_str());
    TEST_ASSERT_EQUAL_UINT32(0, power.waitMinOff());
    TEST_ASSERT_EQUAL_STRING("W3800", pin.log.c_str());
    TEST_ASSERT_FALSE(power.isOn());
}

void test_wait_min_off_not_after_restore_long_off_or_while_on()
{
    RecordingPin pin;
    PiPower power(pin, 5000);
    power.restore(false);                          // aus seit einem frueheren Durchlauf
    TEST_ASSERT_EQUAL_UINT32(0, power.waitMinOff());
    power.restore(true);
    TEST_ASSERT_EQUAL_UINT32(0, power.waitMinOff());   // an
    power.switchTo(false);
    pin.now += 5000;                               // schon lange genug aus
    pin.log.clear();
    TEST_ASSERT_EQUAL_UINT32(0, power.waitMinOff());
    TEST_ASSERT_EQUAL_STRING("", pin.log.c_str());

    PiPower plain(pin);                            // ohne Mindestzeit
    plain.restore(true);
    plain.switchTo(false);
    pin.log.clear();
    TEST_ASSERT_EQUAL_UINT32(0, plain.waitMinOff());
    TEST_ASSERT_EQUAL_STRING("", pin.log.c_str());
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
    RUN_TEST(test_wait_min_off_waits_out_the_rest_after_switch_off);
    RUN_TEST(test_wait_min_off_not_after_restore_long_off_or_while_on);
    return UNITY_END();
}

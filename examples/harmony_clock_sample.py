"""
Minimal HarmonyOS property sample for Kea2.

Run (device Connected, Clock installed):
  kea2 run --platform harmony -s <SERIAL> -p com.huawei.hmos.clock \\
    --running-minutes 3 --max-step 20 --throttle 800 \\
    propertytest examples.harmony_clock_sample
"""
import unittest

from kea2 import precondition


class ClockHarmonyProperties(unittest.TestCase):
    @precondition(
        lambda self: self.d(text="Alarm").exists()
        or self.d(text="World clock").exists()
        or self.d(text="Stopwatch").exists()
    )
    def test_tab_bar_reachable(self):
        # If Alarm tab is visible, tapping it must keep the tab chrome alive.
        if self.d(text="Alarm").exists():
            self.d(text="Alarm").click()
            assert self.d(text="Alarm").exists() or self.d(text="Timer").exists()

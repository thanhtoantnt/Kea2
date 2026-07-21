"""Manual Kea2 — 小猿优课."""
import unittest
from kea2 import precondition
class HuskyProperties(unittest.TestCase):
    @precondition(lambda self: self.d(text="首页").exists())
    def test_home_present(self):
        assert self.d(text="首页").exists()
    @precondition(lambda self: self.d(text="首页").exists() and (self.d(text="数学").exists() or self.d(text="语文").exists()))
    def test_subjects(self):
        assert self.d(text="首页").exists()

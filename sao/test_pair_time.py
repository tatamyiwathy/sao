import unittest
import datetime
from sao.pair_time import PairTime

class TestPairTime(unittest.TestCase):
    def test_get_pair_with_values(self):
        start = datetime.datetime(2024, 6, 1, 10, 0)
        end = datetime.datetime(2024, 6, 1, 12, 0)
        pt = PairTime(start, end)
        self.assertEqual(pt.get_pair(), (start, end))

    def test_get_pair_with_none(self):
        pt = PairTime(None, None)
        self.assertEqual(pt.get_pair(), (None, None))

    def test_is_empty_true(self):
        pt = PairTime(None, None)
        self.assertTrue(pt.is_empty())

    def test_is_empty_false_start(self):
        start = datetime.datetime(2024, 6, 1, 10, 0)
        pt = PairTime(start, None)
        self.assertFalse(pt.is_empty())

    def test_is_empty_false_end(self):
        end = datetime.datetime(2024, 6, 1, 12, 0)
        pt = PairTime(None, end)
        self.assertFalse(pt.is_empty())

    def test_is_empty_false_both(self):
        start = datetime.datetime(2024, 6, 1, 10, 0)
        end = datetime.datetime(2024, 6, 1, 12, 0)
        pt = PairTime(start, end)
        self.assertFalse(pt.is_empty())

if __name__ == '__main__':
    unittest.main()
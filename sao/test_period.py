import unittest
import datetime
from sao.period import Period

class TestPeriod(unittest.TestCase):
    def test_get_pair_with_values(self):
        start = datetime.datetime(2024, 6, 1, 10, 0)
        end = datetime.datetime(2024, 6, 1, 12, 0)
        pt = Period(start, end)
        self.assertEqual(pt.get_pair(), (start, end))

    def test_get_pair_with_none(self):
        pt = Period(None, None)
        self.assertEqual(pt.get_pair(), (None, None))

    def test_is_empty_true(self):
        pt = Period(None, None)
        self.assertTrue(pt.is_empty())

    def test_is_empty_false_start(self):
        start = datetime.datetime(2024, 6, 1, 10, 0)
        pt = Period(start, None)
        self.assertFalse(pt.is_empty())

    def test_is_empty_false_end(self):
        end = datetime.datetime(2024, 6, 1, 12, 0)
        pt = Period(None, end)
        self.assertFalse(pt.is_empty())

    def test_is_empty_false_both(self):
        start = datetime.datetime(2024, 6, 1, 10, 0)
        end = datetime.datetime(2024, 6, 1, 12, 0)
        pt = Period(start, end)
        self.assertFalse(pt.is_empty())

    def test_range(self):
        start = datetime.datetime(2024, 6, 1, 10, 0)
        end = datetime.datetime(2024, 6, 30, 10, 0)
        pt = Period(start, end)
        for t in pt.range():
            self.assertTrue(start <= t < end)


if __name__ == '__main__':
    unittest.main()
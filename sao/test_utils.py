import unittest
from unittest.mock import patch, MagicMock
import datetime

import sao.utils as utils
from common.utils_for_test import create_employee, create_user


class TestIsOverHalfWorkingHours(unittest.TestCase):
    def setUp(self):
        # Dummy employee, not used in logic but required by signature
        self.employee = MagicMock()

    def test_target_time_before_half(self):
        begin = datetime.datetime(2024, 6, 1, 9, 0, 0)
        end = datetime.datetime(2024, 6, 1, 18, 0, 0)
        half = begin + (end - begin) / 2
        # 1 second before half
        target = half - datetime.timedelta(seconds=1)
        self.assertFalse(utils.is_over_half_working_hours(self.employee, (begin, end), target))

    def test_target_time_at_half(self):
        begin = datetime.datetime(2024, 6, 1, 9, 0, 0)
        end = datetime.datetime(2024, 6, 1, 18, 0, 0)
        half = begin + (end - begin) / 2
        target = half
        self.assertFalse(utils.is_over_half_working_hours(self.employee, (begin, end), target))

    def test_target_time_after_half(self):
        begin = datetime.datetime(2024, 6, 1, 9, 0, 0)
        end = datetime.datetime(2024, 6, 1, 18, 0, 0)
        half = begin + (end - begin) / 2
        # 1 second after half
        target = half + datetime.timedelta(seconds=1)
        self.assertTrue(utils.is_over_half_working_hours(self.employee, (begin, end), target))

    def test_target_time_equals_end(self):
        begin = datetime.datetime(2024, 6, 1, 9, 0, 0)
        end = datetime.datetime(2024, 6, 1, 18, 0, 0)
        target = end
        self.assertTrue(utils.is_over_half_working_hours(self.employee, (begin, end), target))

    def test_zero_length_working_hours(self):
        begin = datetime.datetime(2024, 6, 1, 9, 0, 0)
        end = begin
        target = begin
        self.assertFalse(utils.is_over_half_working_hours(self.employee, (begin, end), target))
        target = begin + datetime.timedelta(seconds=1)
        self.assertTrue(utils.is_over_half_working_hours(self.employee, (begin, end), target))

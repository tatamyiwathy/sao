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
        self.assertFalse(utils.is_over_half_working_hours(target, self.employee, (begin, end)))

    def test_target_time_at_half(self):
        begin = datetime.datetime(2024, 6, 1, 9, 0, 0)
        end = datetime.datetime(2024, 6, 1, 18, 0, 0)
        half = begin + (end - begin) / 2
        target = half
        self.assertFalse(utils.is_over_half_working_hours(target, self.employee, (begin, end)))

    def test_target_time_after_half(self):
        begin = datetime.datetime(2024, 6, 1, 9, 0, 0)
        end = datetime.datetime(2024, 6, 1, 18, 0, 0)
        half = begin + (end - begin) / 2
        # 1 second after half
        target = half + datetime.timedelta(seconds=1)
        self.assertTrue(utils.is_over_half_working_hours(target, self.employee, (begin, end)))

    def test_target_time_equals_end(self):
        begin = datetime.datetime(2024, 6, 1, 9, 0, 0)
        end = datetime.datetime(2024, 6, 1, 18, 0, 0)
        target = end
        self.assertTrue(utils.is_over_half_working_hours(target, self.employee, (begin, end)))

    def test_zero_length_working_hours(self):
        begin = datetime.datetime(2024, 6, 1, 9, 0, 0)
        end = begin
        target = begin
        self.assertFalse(utils.is_over_half_working_hours(target, self.employee, (begin, end)))
        target = begin + datetime.timedelta(seconds=1)
        self.assertTrue(utils.is_over_half_working_hours(target, self.employee, (begin, end)))

class TestGenerateDailyRecord(unittest.TestCase):
    def setUp(self):
        self.employee = MagicMock()
        self.date = datetime.date(2024, 6, 1)

    @patch("sao.utils.models.EmployeeDailyRecord")
    def test_no_stamps_creates_empty_record(self, mock_emp_daily_record):
        utils.generate_daily_record([], self.employee, self.date)
        mock_emp_daily_record.assert_called_once_with(
            employee=self.employee,
            date=self.date,
            flag="",
            clock_in=None,
            clock_out=None,
            status=utils.working_status.WorkingStatus.C_KEKKIN,
        )
        mock_emp_daily_record.return_value.save.assert_called_once()

    @patch("sao.utils.models.EmployeeDailyRecord")
    @patch("sao.utils.core.get_employee_hour")
    @patch("sao.utils.utils.is_over_half_working_hours")
    def test_one_stamp_under_half(self, mock_is_over_half, mock_get_hour, mock_emp_daily_record):
        # Setup working hour
        begin_time = datetime.time(9, 0)
        end_time = datetime.time(18, 0)
        working_hour = MagicMock(begin_time=begin_time, end_time=end_time)
        mock_get_hour.return_value = working_hour
        mock_is_over_half.return_value = False

        stamp = datetime.datetime(2024, 6, 1, 9, 30)
        utils.generate_daily_record([stamp], self.employee, self.date)

        mock_emp_daily_record.assert_called_once_with(
            employee=self.employee,
            date=self.date,
            flag="",
            clock_in=stamp,
            clock_out=None,
            status=utils.working_status.WorkingStatus.C_KINMU,
        )
        mock_emp_daily_record.return_value.save.assert_called_once()

    @patch("sao.utils.models.EmployeeDailyRecord")
    @patch("sao.utils.core.get_employee_hour")
    @patch("sao.utils.utils.is_over_half_working_hours")
    def test_one_stamp_over_half(self, mock_is_over_half, mock_get_hour, mock_emp_daily_record):
        begin_time = datetime.time(9, 0)
        end_time = datetime.time(18, 0)
        working_hour = MagicMock(begin_time=begin_time, end_time=end_time)
        mock_get_hour.return_value = working_hour
        mock_is_over_half.return_value = True

        stamp = datetime.datetime(2024, 6, 1, 15, 0)
        utils.generate_daily_record([stamp], self.employee, self.date)

        mock_emp_daily_record.assert_called_once_with(
            employee=self.employee,
            date=self.date,
            flag="",
            clock_in=None,
            clock_out=stamp,
            status=utils.working_status.WorkingStatus.C_KINMU,
        )
        mock_emp_daily_record.return_value.save.assert_called_once()

    @patch("sao.utils.models.EmployeeDailyRecord")
    @patch("sao.utils.core.get_employee_hour")
    def test_one_stamp_no_assigned_working_hour(self, mock_get_hour, mock_emp_daily_record):
        mock_get_hour.side_effect = utils.core.NoAssignedWorkingHourError
        stamp = datetime.datetime(2024, 6, 1, 10, 0)
        # Should not create any record if NoAssignedWorkingHourError is raised
        utils.generate_daily_record([stamp], self.employee, self.date)
        mock_emp_daily_record.assert_not_called()

    @patch("sao.utils.models.EmployeeDailyRecord")
    def test_two_stamps_creates_record_with_first_and_last(self, mock_emp_daily_record):
        stamp1 = datetime.datetime(2024, 6, 1, 9, 0)
        stamp2 = datetime.datetime(2024, 6, 1, 18, 0)
        utils.generate_daily_record([stamp1, stamp2], self.employee, self.date)
        mock_emp_daily_record.assert_called_once_with(
            employee=self.employee,
            date=self.date,
            flag="",
            clock_in=stamp1,
            clock_out=stamp2,
            status=utils.working_status.WorkingStatus.C_KINMU,
        )
        mock_emp_daily_record.return_value.save.assert_called_once()

    @patch("sao.utils.models.EmployeeDailyRecord")
    def test_multiple_stamps_creates_record_with_first_and_last(self, mock_emp_daily_record):
        stamps = [
            datetime.datetime(2024, 6, 1, 8, 55),
            datetime.datetime(2024, 6, 1, 12, 0),
            datetime.datetime(2024, 6, 1, 18, 5),
        ]
        utils.generate_daily_record(stamps, self.employee, self.date)
        mock_emp_daily_record.assert_called_once_with(
            employee=self.employee,
            date=self.date,
            flag="",
            clock_in=stamps[0],
            clock_out=stamps[-1],
            status=utils.working_status.WorkingStatus.C_KINMU,
        )
        mock_emp_daily_record.return_value.save.assert_called_once()




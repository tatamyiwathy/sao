import unittest
from sao.working_status import determine_working_status, WorkingStatus



class TestGetWorkingStatus(unittest.TestCase):
    def test_holiday_no_stamp(self):
        # 休日で記録なし
        self.assertEqual(
            determine_working_status(is_holiday=True, is_legal_holiday=False, has_stamp=False),
            WorkingStatus.C_KYUJITU
        )

    def test_legal_holiday_no_stamp(self):
        # 法定休日で記録なし
        self.assertEqual(
            determine_working_status(is_holiday=True, is_legal_holiday=True, has_stamp=False),
            WorkingStatus.C_KYUJITU
        )

    def test_holiday_with_stamp(self):
        # 法定外休日出勤
        self.assertEqual(
            determine_working_status(is_holiday=True, is_legal_holiday=False, has_stamp=True),
            WorkingStatus.C_HOUTEIGAI_KYUJITU
        )

    def test_legal_holiday_with_stamp(self):
        # 法定休日出勤
        self.assertEqual(
            determine_working_status(is_holiday=True, is_legal_holiday=True, has_stamp=True),
            WorkingStatus.C_HOUTEI_KYUJITU
        )

    def test_weekday_no_stamp(self):
        # 平日で記録なし
        self.assertEqual(
            determine_working_status(is_holiday=False, is_legal_holiday=False, has_stamp=False),
            WorkingStatus.C_KEKKIN
        )

    def test_weekday_with_stamp(self):
        # 平日出勤
        self.assertEqual(
            determine_working_status(is_holiday=False, is_legal_holiday=False, has_stamp=True),
            WorkingStatus.C_KINMU
        )

    def test_invalid_legal_holiday(self):
        # 法定休日なのに休日でない場合は例外
        with self.assertRaises(ValueError):
            determine_working_status(is_holiday=False, is_legal_holiday=True, has_stamp=False)


if __name__ == "__main__":
    unittest.main()

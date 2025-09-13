import datetime


class Const:
    TD_ZERO = datetime.timedelta(seconds=0)
    TD_1H = datetime.timedelta(seconds=1 * 3600)
    TD_2H = datetime.timedelta(seconds=2 * 3600)
    TD_3H = datetime.timedelta(seconds=3 * 3600)
    TD_4H = datetime.timedelta(seconds=4 * 3600)
    TD_5H = datetime.timedelta(seconds=5 * 3600)
    TD_6H = datetime.timedelta(seconds=6 * 3600)
    TD_7H = datetime.timedelta(seconds=7 * 3600)
    TD_8H = datetime.timedelta(seconds=8 * 3600)
    TD_9H = datetime.timedelta(seconds=9 * 3600)

    OCLOCK_0000 = datetime.time(hour=0)
    OCLOCK_0930 = datetime.time(hour=9, minute=30)
    OCLOCK_1000 = datetime.time(hour=10)
    OCLOCK_1030 = datetime.time(hour=10, minute=30)
    OCLOCK_1100 = datetime.time(hour=11)
    OCLOCK_1200 = datetime.time(hour=12)
    OCLOCK_1300 = datetime.time(hour=13)
    OCLOCK_1400 = datetime.time(hour=14)
    OCLOCK_1500 = datetime.time(hour=15)
    OCLOCK_1600 = datetime.time(hour=16)
    OCLOCK_1730 = datetime.time(hour=17, minute=30)
    OCLOCK_1800 = datetime.time(hour=18)
    OCLOCK_1900 = datetime.time(hour=19)
    OCLOCK_1930 = datetime.time(hour=19, minute=30)
    OCLOCK_2000 = datetime.time(hour=20)
    OCLOCK_2100 = datetime.time(hour=21)

    NIGHT_WORK_START = datetime.time(hour=22)
    FIXED_OVERTIME_HOURS_20 = datetime.timedelta(hours=20)  # 20時間/月

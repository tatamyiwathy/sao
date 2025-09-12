class WorkingStatus:
    """勤務状態を表す定数"""

    C_NONE = 0
    C_KINMU = 1
    C_KEKKIN = 2
    C_KYUJITU = 3
    C_HOUTEI_KYUJITU = 4
    C_HOUTEIGAI_KYUJITU = 5
    C_YUUKYUU = 6
    C_DAIKYUU = 7
    C_TOKUBETUKYUU = 8
    C_GOZENKYUU = 9  # 未使用    有給/代休/特別休の午前休を使用する
    C_GOGOKYUU_NASI = 10  # 未使用    有給/代休/特別休の午後休(休息なし)を使用する
    C_GOGOKYUU_ARI = 11  # 未使用    有給/代休/特別休の午後休(休息あり)を使用する
    C_SONOTA = 12
    C_YOTEI = 13
    C_HOUTEI_KYUJITU_GOGOKYU_NASHI = 14
    C_HOUTEI_KYUJITU_GOGOKYU_ARI = 15
    C_HOUTEIGAI_KYUJITU_GOGOKYU_NASHI = 16
    C_HOUTEIGAI_KYUJITU_GOGOKYU_ARI = 17
    C_YUUKYUU_GOZENKYU = 18
    C_YUUKYUU_GOGOKYUU_NASHI = 19
    C_YUUKYUU_GOGOKYUU_ARI = 20
    C_DAIKYUU_GOZENKYU = 21
    C_DAIKYUU_GOGOKYUU_NASHI = 22
    C_DAIKYUU_GOGOKYUU_ARI = 23
    C_TOKUBETUKYUU_GOZENKYU = 24
    C_TOKUBETUKYUU_GOGOKYUU_NASHI = 25
    C_TOKUBETUKYUU_GOGOKYUU_ARI = 26
    C_HOUTEI_KYUJITU_GOZENKYUU = 27
    C_HOUTEIGAI_KYUJITU_GOZENKYUU = 28

    choices = (
        (C_NONE, "未確定"),
        (C_KINMU, "勤務"),
        (C_KEKKIN, "欠勤"),
        (C_KYUJITU, "休日"),
        (C_HOUTEI_KYUJITU, "休出（法定）"),
        (C_HOUTEI_KYUJITU_GOZENKYUU, "休出（法定）午前休"),
        (C_HOUTEI_KYUJITU_GOGOKYU_NASHI, "休出（法定）午後休（休息なし）"),
        (C_HOUTEI_KYUJITU_GOGOKYU_ARI, "休出（法定）午後休（休息あり）"),
        (C_HOUTEIGAI_KYUJITU, "休出（法定外）"),
        (C_HOUTEIGAI_KYUJITU_GOZENKYUU, "休出（法定外）午前休"),
        (C_HOUTEIGAI_KYUJITU_GOGOKYU_NASHI, "休出（法定外）午後休（休息なし）"),
        (C_HOUTEIGAI_KYUJITU_GOGOKYU_ARI, "休出（法定外）午後休（休息あり）"),
        (C_YUUKYUU, "有休"),
        (C_YUUKYUU_GOZENKYU, "有休-午前休"),
        (C_YUUKYUU_GOGOKYUU_NASHI, "有休-午後休（休息なし）"),
        (C_YUUKYUU_GOGOKYUU_ARI, "有休-午後休（休息あり）"),
        (C_DAIKYUU, "代休"),
        (C_DAIKYUU_GOZENKYU, "代休-午前休"),
        (C_DAIKYUU_GOGOKYUU_NASHI, "代休-午後休（休息なし）"),
        (C_DAIKYUU_GOGOKYUU_ARI, "代休-午後休（休息あり）"),
        (C_TOKUBETUKYUU, "特別休"),
        (C_TOKUBETUKYUU_GOZENKYU, "特別休-午前休"),
        (C_TOKUBETUKYUU_GOGOKYUU_NASHI, "特別休-午後休（休息なし）"),
        (C_TOKUBETUKYUU_GOGOKYUU_ARI, "特別休-午後休（休息あり）"),
        (C_SONOTA, "その他"),
        (C_YOTEI, "予定"),
    )

    # 休日出勤ステータス
    HOLIDAY_WORK = [
        C_HOUTEI_KYUJITU,
        C_HOUTEIGAI_KYUJITU,
        C_HOUTEI_KYUJITU_GOZENKYUU,
        C_HOUTEI_KYUJITU_GOGOKYU_NASHI,
        C_HOUTEI_KYUJITU_GOGOKYU_ARI,
        C_HOUTEI_KYUJITU_GOGOKYU_ARI,
        C_HOUTEIGAI_KYUJITU_GOZENKYUU,
        C_HOUTEIGAI_KYUJITU_GOGOKYU_NASHI,
        C_HOUTEIGAI_KYUJITU_GOGOKYU_ARI,
    ]

    # 休日ステータス
    HOLIDAY = [
        C_KYUJITU,
        C_HOUTEI_KYUJITU,
        C_HOUTEIGAI_KYUJITU,
    ]

    # 午後休・休息あり
    AFTERNOON_OFF_WITH_REST = [
        C_GOGOKYUU_ARI,
        C_HOUTEI_KYUJITU_GOGOKYU_ARI,
        C_HOUTEIGAI_KYUJITU_GOGOKYU_ARI,
        C_YUUKYUU_GOGOKYUU_ARI,
        C_DAIKYUU_GOGOKYUU_ARI,
        C_TOKUBETUKYUU_GOGOKYUU_ARI,
    ]

    # 午後休・休息なし
    AFTERNOON_OFF_NO_REST = [
        C_GOGOKYUU_NASI,
        C_HOUTEI_KYUJITU_GOGOKYU_NASHI,
        C_HOUTEIGAI_KYUJITU_GOGOKYU_NASHI,
        C_YUUKYUU_GOGOKYUU_NASHI,
        C_DAIKYUU_GOGOKYUU_NASHI,
        C_TOKUBETUKYUU_GOGOKYUU_NASHI,
    ]

    # 午前休
    MORNING_OFF = [
        C_GOZENKYUU,
        C_YUUKYUU_GOZENKYU,
        C_DAIKYUU_GOZENKYU,
        C_TOKUBETUKYUU_GOZENKYU,
        C_HOUTEI_KYUJITU_GOZENKYUU,
        C_HOUTEIGAI_KYUJITU_GOZENKYUU,
    ]

    # 勤務なし
    NO_ACTUAL_WORK = [
        C_KEKKIN,
        C_KYUJITU,
        C_YUUKYUU,
        C_DAIKYUU,
        C_TOKUBETUKYUU,
    ]


def determine_working_status(
    is_holiday: bool, is_legal_holiday: bool, has_stamp: bool
) -> int:
    """
    ☑勤務状態を判定する

    :param is_holiday: 休日か
    :param is_legal_holiday: 法定休日か
    :param has_stamp: 打刻があるか(どちらか一方があればよい)
    :return: WorkingStatusの定数
    """
    if is_holiday is False and is_legal_holiday is True:
        raise ValueError("法定休日のときは休日でなければなりません")

        # holiday, legal_hokiday, has_stamp, status
    conditions = [
        (True, False, False, WorkingStatus.C_KYUJITU),  # 休日で記録なし
        (True, True, False, WorkingStatus.C_KYUJITU),  # 法的休日で記録なし
        (True, False, True, WorkingStatus.C_HOUTEIGAI_KYUJITU),  # 法定外休日出勤
        (True, True, True, WorkingStatus.C_HOUTEI_KYUJITU),  # 法定休日出勤
        (False, False, False, WorkingStatus.C_KEKKIN),  # 平日で記録なし
        (False, False, True, WorkingStatus.C_KINMU),  # 平日出勤
    ]

    for c in conditions:
        if (c[0] == is_holiday) and (c[1] == is_legal_holiday) and (c[2] == has_stamp):
            return c[3]

    return WorkingStatus.C_NONE

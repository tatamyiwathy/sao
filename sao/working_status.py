class WorkingStatus:
    (
        C_NONE,
        C_KINMU,
        C_KEKKIN,
        C_KYUJITU,
        C_HOUTEI_KYUJITU,
        C_HOUTEIGAI_KYUJITU,
        C_YUUKYUU,
        C_DAIKYUU,
        C_TOKUBETUKYUU,
        C_GOZENKYUU,  # 未使用    有給/代休/特別休の午前休を使用する
        C_GOGOKYUU_NASI,  # 未使用    有給/代休/特別休の午後休(休息なし)を使用する
        C_GOGOKYUU_ARI,  # 未使用    有給/代休/特別休の午後休(休息あり)を使用する
        C_SONOTA,
        C_YOTEI,
        C_HOUTEI_KYUJITU_GOGOKYU_NASHI,
        C_HOUTEI_KYUJITU_GOGOKYU_ARI,
        C_HOUTEIGAI_KYUJITU_GOGOKYU_NASHI,
        C_HOUTEIGAI_KYUJITU_GOGOKYU_ARI,
        C_YUUKYUU_GOZENKYU,
        C_YUUKYUU_GOGOKYUU_NASHI,
        C_YUUKYUU_GOGOKYUU_ARI,
        C_DAIKYUU_GOZENKYU,
        C_DAIKYUU_GOGOKYUU_NASHI,
        C_DAIKYUU_GOGOKYUU_ARI,
        C_TOKUBETUKYUU_GOZENKYU,
        C_TOKUBETUKYUU_GOGOKYUU_NASHI,
        C_TOKUBETUKYUU_GOGOKYUU_ARI,
        C_HOUTEI_KYUJITU_GOZENKYUU,
        C_HOUTEIGAI_KYUJITU_GOZENKYUU,
    ) = range(0, 29)

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

import datetime


class Period:
    def __init__(self, start: datetime.datetime | None, end: datetime.datetime | None):
        self.start = start
        self.end = end

    def get_pair(self) -> tuple[datetime.datetime | None, datetime.datetime | None]:
        return (self.start, self.end)

    def is_empty(self) -> bool:
        """開始時間も終了時間もNoneならTrueを返す"""
        return self.start is None and self.end is None

    def is_unset(self) -> bool:
        """開始時間か終了時間のどちらかがNoneならTrueを返す"""
        return self.start is None or self.end is None

    def is_filled(self) -> bool:
        """開始時間も終了時間もNoneでなければTrueを返す"""
        return self.start is not None and self.end is not None

    def duration(self) -> datetime.timedelta:
        """終了時間 - 開始時間 を返す。どちらかがNoneならNoneを返す"""
        if self.start is None or self.end is None:
            raise ValueError("Both start and end must be set to calculate duration.")
        return self.end - self.start

    def range(self, step: datetime.timedelta = datetime.timedelta(days=1)):
        """
        startからendまで、step間隔でdatetimeをyieldするイテレータを返す。

        Args:
            step (datetime.timedelta): 増分。デフォルトは1日。
        """
        if self.start is None or self.end is None:
            return
        current = self.start
        while current < self.end:
            yield current
            current += step

    def __str__(self) -> str:
        return f"Period(start={self.start}, end={self.end})"

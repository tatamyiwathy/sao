import datetime

class PairTime:
    def __init__(self, start: datetime.datetime | None, end: datetime.datetime | None):
        self.start = start
        self.end = end
    
    def get_pair(self) -> tuple[datetime.datetime | None, datetime.datetime | None]:
        return (self.start, self.end)
    
    def is_empty(self) -> bool:
        return self.start is None and self.end is None
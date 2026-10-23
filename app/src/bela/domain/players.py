from enum import IntEnum


class Seat(IntEnum):
    ZERO = 0
    ONE = 1
    TWO = 2
    THREE = 3

    @property
    def next(self) -> "Seat":
        return Seat((int(self) + 1) % 4)

    @property
    def partner(self) -> "Seat":
        return Seat((int(self) + 2) % 4)

    @property
    def team(self) -> int:
        return int(self) % 2

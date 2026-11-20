"""Reuse identical first tie-break draws across paired candidate branches."""

from random import Random


class _FirstDraw:
    __slots__ = ('seed', 'values', 'used')

    def __init__(self, seed):
        self.seed, self.values, self.used = seed, {}, False

    def randrange(self, stop):
        # Current policies and self search make exactly one tie-break draw.
        # Fail explicitly if that contract changes instead of reusing a draw
        # where an independent second draw would be required.
        if self.used:
            raise RuntimeError('A rollout move requested more than one random draw')
        if type(stop) is not int or stop <= 0:
            raise ValueError('Expected a positive number of tie-break choices')
        self.used = True
        try:
            return self.values[stop]
        except KeyError:
            value = Random(self.seed).randrange(stop)
            self.values[stop] = value
            return value


class TrialRandomness:
    """One trial only; do not share cached draws between independent trials.

    Keys include both card position and choice count. Results exactly match
    Random((trial_seed << 6) + ply).randrange(stop), including rejection behavior.
    No modulo approximation, opponent hand or policy identity enters the key.
    """

    __slots__ = ('seed', 'positions')

    def __init__(self, seed):
        self.seed, self.positions = seed << 6, {}

    def at(self, ply):
        try:
            draw = self.positions[ply]
        except KeyError:
            draw = self.positions[ply] = _FirstDraw(self.seed + ply)
        draw.used = False
        return draw

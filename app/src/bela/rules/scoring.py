from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DealResult:
    earned: tuple[int, int]
    recorded: tuple[int, int]
    caller_team: int
    caller_passed: bool
    total: int


def settle_deal(
    *,
    card_points: tuple[int, int],
    trick_counts: tuple[int, int],
    last_trick_team: int,
    caller_team: int,
    awarded_melds: tuple[int, int] = (0, 0),
    announced_bela: tuple[int, int] = (0, 0),
) -> DealResult:
    """Settle a finished deal, given already validated declaration results.

    awarded_melds contains only the ordinary-meld contest winner's points.
    announced_bela contains timely declarations (0 or 20 per team).
    Detecting and comparing melds and validating bela timing belong upstream.
    Belot terminates a match separately and must not be passed here.
    """
    pairs = (card_points, trick_counts, awarded_melds, announced_bela)
    if any(len(pair) != 2 or any(type(n) is not int or n < 0 for n in pair)
           for pair in pairs):
        raise ValueError("Expected pairs of nonnegative integers")
    if last_trick_team not in (0, 1) or caller_team not in (0, 1):
        raise ValueError("Teams must be 0 or 1")
    if sum(card_points) != 152 or sum(trick_counts) != 8:
        raise ValueError("A completed deal has 152 card points and eight tricks")
    if not trick_counts[last_trick_team]:
        raise ValueError("Last-trick winner must have won a trick")
    if any(not trick_counts[t] and card_points[t] for t in (0, 1)):
        raise ValueError("A team without tricks cannot have card points")
    if all(awarded_melds) or any(n % 10 for n in awarded_melds):
        raise ValueError("Ordinary meld points must be awarded to at most one team")
    if any(n not in (0, 20) for n in announced_bela) or sum(announced_bela) > 20:
        raise ValueError("Only one timely bela is possible in a deal")
    earned = list(card_points)
    earned[last_trick_team] += 10
    for team in (0, 1):
        if trick_counts[team] == 8:
            earned[team] += 90
        if trick_counts[team]:
            earned[team] += awarded_melds[team] + announced_bela[team]
    total = sum(earned)
    passed = 2 * earned[caller_team] > total
    recorded = earned.copy() if passed else [0, 0]
    if not passed:
        recorded[1 - caller_team] = total
    return DealResult(tuple(earned), tuple(recorded), caller_team, passed, total)


def match_winner(score: tuple[int, int]) -> int | None:
    """Call after settlement; equal totals above 1000 require another deal."""
    if len(score) != 2 or any(type(n) is not int or n < 0 for n in score):
        raise ValueError("Expected two nonnegative integer scores")
    if max(score) <= 1000 or score[0] == score[1]:
        return None
    return 0 if score[0] > score[1] else 1

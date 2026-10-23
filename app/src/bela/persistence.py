"""Versioned JSON archives validated by replay, written using atomic replacement.

These are full simulator saves containing all four private hands. They are not
the future partial-information user-session format or a public game export.
"""

import json
import os
import tempfile
from pathlib import Path
from uuid import UUID

from bela import RULESET_VERSION
from bela.domain.cards import Card, Rank, Suit
from bela.domain.game import Phase, PlayState, Seat
from bela.domain.melds import MeldValueAnnouncement, SequenceHighAnnouncement
from bela.session import MatchSession, initial_hands
from bela.simulation import (announce_meld_value, announce_sequence_high, declare_belot,
                             play_card, resolve_declarations, start_play)


SCHEMA_VERSION = 1
MAX_SAVE_BYTES = 8 * 1024 * 1024


class InvalidSaveError(ValueError):
    """Malformed, inconsistent, or unsupported match archive."""


def _object(value, keys: set[str], where: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise InvalidSaveError(f"{where}: expected fields {', '.join(sorted(keys))}")
    return value


def _int(value, where: str, *, minimum=0, maximum=None) -> int:
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise InvalidSaveError(f"{where}: invalid integer")
    return value


def _seat(value) -> Seat:
    return Seat(_int(value, "player", maximum=3))


def _card(value) -> Card:
    if not isinstance(value, str) or len(value) > 4:
        raise InvalidSaveError("Invalid card code")
    card = Card.parse(value)
    if str(card) != value:
        raise InvalidSaveError("Expected a canonical card code such as H_J")
    return card


def _replay(record) -> PlayState:
    record = _object(record, {"initial", "actions"}, "deal")
    config = _object(record["initial"], {"hands", "trump", "dealer", "caller", "match_score"}, "initial")
    hands, score = config["hands"], config["match_score"]
    if not isinstance(hands, list) or len(hands) != 4:
        raise InvalidSaveError("Expected four initial hands")
    if any(not isinstance(hand, list) or len(hand) != 8 for hand in hands):
        raise InvalidSaveError("Each initial hand must contain eight cards")
    if not isinstance(score, list) or len(score) != 2:
        raise InvalidSaveError("Expected a pair of match scores")
    if not isinstance(config["trump"], str):
        raise InvalidSaveError("Invalid trump")
    state = start_play(tuple(tuple(_card(c) for c in hand) for hand in hands),
                       trump=Suit(config["trump"]), dealer=_seat(config["dealer"]),
                       caller=_seat(config["caller"]),
                       match_score=tuple(_int(n, "match score") for n in score))
    actions = record["actions"]
    if not isinstance(actions, list) or len(actions) > 64:
        raise InvalidSaveError("Expected at most 64 actions per deal")
    for index, action in enumerate(actions):
        if not isinstance(action, dict) or not isinstance(action.get("type"), str):
            raise InvalidSaveError(f"Action {index}: missing action type")
        kind = action["type"]
        try:
            if kind == "meld_value":
                _object(action, {"type", "player", "points"}, "meld value")
                expected = _int(action["points"], "meld points")
                state = announce_meld_value(state, _seat(action["player"]))
                if state.meld_announcements[-1].points != expected:
                    raise InvalidSaveError("Announced value does not match the hand")
            elif kind == "sequence_high":
                _object(action, {"type", "player", "rank"}, "sequence endpoint")
                if not isinstance(action["rank"], str):
                    raise InvalidSaveError("Invalid sequence endpoint")
                expected = Rank(action["rank"])
                state = announce_sequence_high(state, _seat(action["player"]))
                if state.meld_announcements[-1].rank != expected:
                    raise InvalidSaveError("Announced endpoint does not match the hand")
            elif kind == "resolve_declarations":
                _object(action, {"type"}, "declaration resolution")
                state = resolve_declarations(state)
            elif kind == "play_card":
                _object(action, {"type", "player", "card", "bela"}, "card play")
                if type(action["bela"]) is not bool:
                    raise InvalidSaveError("Bela flag must be true or false")
                state = play_card(state, _seat(action["player"]), _card(action["card"]),
                                  announce_bela=action["bela"])
            elif kind == "belot":
                _object(action, {"type", "player"}, "belot")
                state = declare_belot(state, _seat(action["player"]))
            else:
                raise InvalidSaveError(f"Unknown action type: {kind}")
        except ValueError as error:
            raise InvalidSaveError(f"Action {index + 1} ({kind}): {error}") from error
    return state


def _record(state: PlayState) -> dict:
    """Serialize canonical actions, then verify they recreate the exact state."""
    if not isinstance(state, PlayState):
        raise InvalidSaveError("Expected a PlayState")
    if any(len(trick.cards) != 4 for trick in state.completed_tricks):
        raise InvalidSaveError("Completed tricks must contain four cards")
    if len(state.completed_tricks) > 8 or len(state.current_trick.cards) > 3:
        raise InvalidSaveError("Invalid trick history")
    actions = []
    for claim in state.meld_announcements:
        if isinstance(claim, MeldValueAnnouncement):
            actions.append({"type": "meld_value", "player": int(claim.player), "points": claim.points})
        elif isinstance(claim, SequenceHighAnnouncement):
            actions.append({"type": "sequence_high", "player": int(claim.player), "rank": claim.rank.value})
        else:
            raise InvalidSaveError("Unknown declaration record")
    if state.meld_contest is not None:
        actions.append({"type": "resolve_declarations"})
    if state.belot is not None:
        actions.append({"type": "belot", "player": int(state.belot.winner)})
    bela_positions = {(call.trick_index, call.position) for call in state.bela_announcements}
    for trick_index, trick in enumerate((*state.completed_tricks, state.current_trick)):
        for position, card in enumerate(trick.cards):
            actions.append({"type": "play_card", "player": int(trick.seat_at(position)),
                            "card": str(card), "bela": (trick_index, position) in bela_positions})
    record = {
        "initial": {"hands": [[str(c) for c in hand] for hand in initial_hands(state)],
                    "trump": state.trump.value, "dealer": int(state.dealer),
                    "caller": int(state.caller), "match_score": list(state.match_score)},
        "actions": actions,
    }
    if _replay(record) != state:
        raise InvalidSaveError("Stored state is inconsistent with its legal play history")
    return record


def _validate_chain(session: MatchSession) -> None:
    if not isinstance(session.id, str) or str(UUID(session.id)) != session.id:
        raise InvalidSaveError("Invalid match ID")
    if not isinstance(session.name, str) or not session.name.strip() or len(session.name) > 200:
        raise InvalidSaveError("Invalid match name")
    if not isinstance(session.deals, tuple) or not 1 <= len(session.deals) <= 1000:
        raise InvalidSaveError("Expected 1–1000 deals")
    from bela.rules.scoring import match_winner

    if match_winner(session.deals[0].match_score) is not None:
        raise InvalidSaveError("The match was already won before its first saved deal")
    for index in range(1, len(session.deals)):
        previous = MatchSession(session.id, session.name, session.deals[:index])
        current = session.deals[index]
        if not previous.current.finished or previous.winner is not None:
            raise InvalidSaveError(f"Deal {index + 1} cannot follow an unfinished or won match")
        if current.match_score != previous.score or current.dealer != previous.current.dealer.next:
            raise InvalidSaveError(f"Deal {index + 1} has an inconsistent score or dealer")


def dumps_match(session: MatchSession) -> str:
    """Encode a fully validated archive. No pickle or executable object format."""
    try:
        if not isinstance(session, MatchSession):
            raise InvalidSaveError("Expected a MatchSession")
        records = [_record(state) for state in session.deals]
        _validate_chain(session)
        data = {"schema_version": SCHEMA_VERSION, "ruleset_version": RULESET_VERSION,
                "match": {"id": session.id, "name": session.name, "deals": records}}
        encoded = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if len(encoded.encode("utf-8")) > MAX_SAVE_BYTES:
            raise InvalidSaveError("Match archive exceeds the 8 MiB limit")
        return encoded
    except (TypeError, ValueError, AttributeError, IndexError) as error:
        if isinstance(error, InvalidSaveError):
            raise
        raise InvalidSaveError(f"Cannot save this match: {error}") from error


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidSaveError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise InvalidSaveError(f"Invalid JSON constant: {value}")


def loads_match(text: str) -> MatchSession:
    try:
        if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_SAVE_BYTES:
            raise InvalidSaveError("Expected a JSON archive no larger than 8 MiB")
        data = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        _object(data, {"schema_version", "ruleset_version", "match"}, "archive")
        if type(data["schema_version"]) is not int or data["schema_version"] != SCHEMA_VERSION:
            raise InvalidSaveError("Unsupported save schema version")
        if data["ruleset_version"] != RULESET_VERSION:
            raise InvalidSaveError("Unsupported Bela ruleset version")
        match = _object(data["match"], {"id", "name", "deals"}, "match")
        if not isinstance(match["deals"], list) or not 1 <= len(match["deals"]) <= 1000:
            raise InvalidSaveError("Expected 1–1000 deals")
        session = MatchSession(match["id"], match["name"], tuple(_replay(deal) for deal in match["deals"]))
        _validate_chain(session)
        return session
    except (TypeError, ValueError, KeyError, RecursionError) as error:
        if isinstance(error, InvalidSaveError):
            raise
        raise InvalidSaveError(f"Invalid match archive: {error}") from error


def save_match(session: MatchSession, path: str | Path) -> Path:
    """Validate before touching the target, then replace it in one operation.

    Existing archives are overwritten only after a complete UTF-8 write and
    fsync. A failed write leaves the previous target in place. This does not
    promise cloud-sync conflict handling or power-loss guarantees of the disk.
    """
    return write_archive_text(path, dumps_match(session))


def write_archive_text(path: str | Path, encoded: str) -> Path:
    """Atomic UTF-8 write shared by the separately versioned archive formats."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         prefix=f".{target.name}.", suffix=".tmp",
                                         dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target


def load_match(path: str | Path) -> MatchSession:
    return loads_match(read_archive_text(path))


def read_archive_text(path: str | Path) -> str:
    """Bounded UTF-8 read; schema validation belongs to the format's loader."""
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_SAVE_BYTES + 1)
    if len(raw) > MAX_SAVE_BYTES:
        raise InvalidSaveError("Match archive exceeds the 8 MiB limit")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise InvalidSaveError("Match archives must use UTF-8 encoding") from error
    return text

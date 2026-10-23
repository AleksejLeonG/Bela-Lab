"""Archives containing only supplied knowledge and the complete edit history."""

import json
from uuid import UUID

from bela import RULESET_VERSION
from bela.domain.cards import Suit, Rank
from bela.persistence import (InvalidSaveError, MAX_SAVE_BYTES, _card, _int, _object,
                              _seat, _unique_object, _invalid_constant,
                              read_archive_text, write_archive_text)
from bela.tracking import (AddEvent, Belot, DealSetup, DeleteEvent, FinishDeclarations, InsertEvent,
                           MeldValue, NextDeal, Play, Presence, ReplaceEvent, ReplaceSetup,
                           Reveal, SequenceHigh, UserMatch, ValidationLimit, materialize)


def setup_data(setup):
    return {"player": int(setup.player), "hand": list(map(str, setup.hand)),
            "dealer": int(setup.dealer), "caller": int(setup.caller),
            "trump": setup.trump.value, "match_score": list(setup.match_score)}


def _cards(values, *, allow_empty=False):
    if not isinstance(values, list) or not (0 if allow_empty else 1) <= len(values) <= 8:
        raise InvalidSaveError("Expected a list of at most eight cards.")
    return tuple(_card(card) for card in values)


def _setup(data):
    _object(data, {"player", "hand", "dealer", "caller", "trump", "match_score"}, "setup")
    score = data["match_score"]
    if not isinstance(score, list) or len(score) != 2 or not isinstance(data["trump"], str):
        raise InvalidSaveError("Invalid score or trump.")
    return DealSetup(_seat(data["player"]), _cards(data["hand"]), _seat(data["dealer"]),
                     _seat(data["caller"]), Suit(data["trump"]), tuple(_int(n, "score") for n in score))


def event_data(event):
    if isinstance(event, Presence):
        return {"type": "presence", "player": int(event.player), "has_meld": event.has_meld}
    if isinstance(event, MeldValue):
        return {"type": "meld_value", "player": int(event.player), "points": event.points}
    if isinstance(event, SequenceHigh):
        return {"type": "sequence_high", "player": int(event.player), "rank": event.rank.value}
    if isinstance(event, Reveal):
        return {"type": "reveal", "player": int(event.player), "cards": list(map(str, event.cards))}
    if isinstance(event, FinishDeclarations):
        return {"type": "finish_declarations", "winning_team": event.winning_team}
    if isinstance(event, Play):
        return {"type": "play", "player": int(event.player), "card": str(event.card), "bela": event.bela}
    if isinstance(event, Belot):
        return {"type": "belot", "player": int(event.player), "cards": list(map(str, event.cards))}
    raise InvalidSaveError("Unknown event.")


def _event(data):
    if not isinstance(data, dict):
        raise InvalidSaveError("Invalid event.")
    kind = data.get("type")
    fields = {
        "presence": {"type", "player", "has_meld"},
        "meld_value": {"type", "player", "points"},
        "sequence_high": {"type", "player", "rank"},
        "reveal": {"type", "player", "cards"},
        "finish_declarations": {"type", "winning_team"},
        "play": {"type", "player", "card", "bela"},
        "belot": {"type", "player", "cards"},
    }
    if not isinstance(kind, str) or kind not in fields:
        raise InvalidSaveError("Unknown event type.")
    _object(data, fields[kind], "event")
    if kind == "finish_declarations":
        team = data["winning_team"]
        return FinishDeclarations(None if team is None else _int(team, "team", maximum=1))
    player = _seat(data["player"])
    if kind == "presence":
        if type(data["has_meld"]) is not bool:
            raise InvalidSaveError("Meld presence must be a boolean.")
        return Presence(player, data["has_meld"])
    if kind == "meld_value":
        return MeldValue(player, _int(data["points"], "meld"))
    if kind == "sequence_high":
        if not isinstance(data["rank"], str):
            raise InvalidSaveError("Invalid sequence high card.")
        return SequenceHigh(player, Rank(data["rank"]))
    if kind == "reveal":
        return Reveal(player, _cards(data["cards"]))
    if kind == "belot":
        return Belot(player, _cards(data["cards"], allow_empty=True))
    if type(data["bela"]) is not bool:
        raise InvalidSaveError("Bela announcement must be a boolean.")
    return Play(player, _card(data["card"]), data["bela"])


def _command_data(command):
    if isinstance(command, AddEvent):
        return {"type": "add", "event": event_data(command.event)}
    if isinstance(command, (ReplaceEvent, InsertEvent)):
        return {"type": "replace" if isinstance(command, ReplaceEvent) else "insert",
                "index": command.index, "event": event_data(command.event)}
    if isinstance(command, DeleteEvent):
        return {"type": "delete", "index": command.index}
    if isinstance(command, (ReplaceSetup, NextDeal)):
        return {"type": "setup" if isinstance(command, ReplaceSetup) else "next_deal",
                "setup": setup_data(command.setup)}
    raise InvalidSaveError("Unknown change.")


def _command(data):
    if not isinstance(data, dict):
        raise InvalidSaveError("Invalid change.")
    kind = data.get("type")
    if kind == "add":
        _object(data, {"type", "event"}, "change")
        return AddEvent(_event(data["event"]))
    if kind in ("replace", "insert"):
        _object(data, {"type", "index", "event"}, "change")
        return (ReplaceEvent if kind == "replace" else InsertEvent)(
            _int(data["index"], "index"), _event(data["event"]))
    if kind == "delete":
        _object(data, {"type", "index"}, "change")
        return DeleteEvent(_int(data["index"], "index"))
    if kind in ("setup", "next_deal"):
        _object(data, {"type", "setup"}, "change")
        return (ReplaceSetup if kind == "setup" else NextDeal)(_setup(data["setup"]))
    raise InvalidSaveError("Unknown change.")


def dumps_user_match(match: UserMatch) -> str:
    try:
        if not isinstance(match, UserMatch) or not isinstance(match.id, str) or str(UUID(match.id)) != match.id:
            raise InvalidSaveError("Invalid match identity.")
        if not isinstance(match.name, str) or not match.name.strip() or len(match.name) > 200:
            raise InvalidSaveError("Invalid match name.")
        materialize(match)
        data = {"format": "bela-player-session", "schema_version": 1,
                "ruleset_version": RULESET_VERSION, "id": match.id, "name": match.name,
                "initial": setup_data(match.initial),
                "commands": [_command_data(c) for c in match.commands]}
        encoded = json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
        if len(encoded.encode("utf-8")) > MAX_SAVE_BYTES:
            raise InvalidSaveError("The archive exceeds 8 MiB.")
        return encoded
    except ValidationLimit:
        raise
    except (ValueError, TypeError, AttributeError) as error:
        if isinstance(error, InvalidSaveError):
            raise
        raise InvalidSaveError(f"Invalid player match: {error}") from error


def loads_user_match(text: str) -> UserMatch:
    try:
        if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_SAVE_BYTES:
            raise InvalidSaveError("Expected a JSON archive of at most 8 MiB.")
        data = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        _object(data, {"format", "schema_version", "ruleset_version", "id", "name", "initial", "commands"}, "match")
        if (data["format"] != "bela-player-session" or type(data["schema_version"]) is not int
                or data["schema_version"] != 1 or data["ruleset_version"] != RULESET_VERSION):
            raise InvalidSaveError("Unsupported player archive format, version or ruleset.")
        if not isinstance(data["commands"], list) or len(data["commands"]) > 10_000:
            raise InvalidSaveError("Invalid revision list.")
        match = UserMatch(data["id"], data["name"], _setup(data["initial"]),
                          tuple(_command(c) for c in data["commands"]))
        dumps_user_match(match)  # validates metadata, history, and all corrections
        return match
    except ValidationLimit:
        raise
    except (ValueError, TypeError, KeyError, RecursionError) as error:
        if isinstance(error, InvalidSaveError):
            raise
        raise InvalidSaveError(f"Invalid match archive: {error}") from error


def save_user_match(match, path):
    return write_archive_text(path, dumps_user_match(match))


def load_user_match(path):
    return loads_user_match(read_archive_text(path))

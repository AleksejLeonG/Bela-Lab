"""Read-only replay and feedback attached to exact recorded positions."""

from hashlib import sha256
import json
from random import Random

from bela.analysis.learned_policy import fallback_profile
from bela.analysis.lineups import StrategyLineup
from bela.analysis.policies import announce_bela, choose_move
from bela.analysis.rollout_random import TrialRandomness
from bela.analysis.sampling import HandSampler
from bela.analysis.simulation_bridge import SimulationBridge
from bela.gameplay.simulation import observe, play_card, settle_play

from bela.gameplay.tracking import AddEvent, NextDeal, Play, UserMatch, replay_deal
from bela.storage.persistence import write_archive_text
from bela.storage.user_storage import event_data, loads_user_match, setup_data


def position_key(deals, number, count):
    # Include earlier deals: score and declarations are part of the position.
    history = [{"setup": setup_data(d.setup),
                "events": [event_data(e) for e in d.events[:count if i == number else None]]}
               for i, d in enumerate(deals[:number + 1])]
    return sha256(json.dumps(history, sort_keys=True).encode()).hexdigest()


def read_feedback(storage, match_id):
    path = storage / "review" / f"{match_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def historical_match(match, key):
    """Reconstruct only the supplied knowledge up to the selected decision.

    Rebuild materialized history rather than truncating the edit log: a later
    correction may have established today's recorded version of an earlier move.
    No future event or correction command is serialized into the analysis input.
    """
    commands = []
    for number, deal in enumerate(match.deals):
        if number:
            commands.append(NextDeal(deal.setup))
        for index, event in enumerate(deal.events):
            if isinstance(event, Play) and position_key(match.deals, number, index) == key:
                snapshot = UserMatch(match.id, match.name, match.deals[0].setup, tuple(commands))
                if snapshot.state.next_player != snapshot.state.setup.player:
                    raise ValueError("Only your decisions can be analysed: other players' hands are unknown.")
                return snapshot
            commands.append(AddEvent(event))
    raise ValueError("This position is no longer in the match. Reload the analysis board.")


def review_variations(snapshot, seed, trick_data):
    """Compare legal first moves in one sampled world using the same policy draws."""
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("Invalid continuation seed.")
    tracked = snapshot.state
    own = tracked.setup.player
    bridge = SimulationBridge.from_match(snapshot)
    batch = HandSampler(tracked.evidence, seconds=1).sample(1, seed=seed, seconds=1)
    if not batch.deals:
        raise ValueError("Could not sample a consistent deal. Try another sample.")
    base = bridge.resume(batch.deals[0])
    lineup = StrategyLineup.for_trial(snapshot.id, seed, 0, own)
    own_policy = fallback_profile(snapshot.id, seed, 0)
    randomness = TrialRandomness(Random(seed).getrandbits(128))
    branches = []
    for first_card in tracked.legal_actions:
        state = base
        card = first_card
        steps = []
        while not state.finished:
            player = state.next_player
            view = observe(state, player)
            if steps:
                ply = len(state.completed_tricks) * 4 + len(state.current_trick.cards)
                policy = own_policy if player == own else lineup.for_player(player)
                card = choose_move(view, randomness.at(ply), policy).card
            count = len(state.completed_tricks)
            state = play_card(state, player, card, announce_bela=announce_bela(view, card))
            completed = len(state.completed_tricks) > count
            trick = state.completed_tricks[-1] if completed else state.current_trick
            steps.append({"player": int(player), "card": str(card), "trick_number": count + 1,
                          "trick": trick_data(trick, state.trump, complete=completed),
                          "hand": [str(c) for c in sorted(state.hands[own], key=lambda c: c.id)]})
        result = settle_play(state)
        branches.append({"card": str(first_card), "steps": steps, "recorded": result.recorded,
                         "caller_passed": result.caller_passed})
    return {"our_team": own.team, "branches": branches}


def review_view(match, storage, trick_data):
    notes = read_feedback(storage, match.id)
    advice = {}
    skipped = 0
    for path in sorted((storage / "analysis").glob("*.jsonl")):
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                record = json.loads(line)
                if record.get("format") != "bela-analysis-record" or record.get("input", {}).get("id") != match.id:
                    continue
                original = loads_user_match(json.dumps(record["input"]))
                n = len(original.deals) - 1
                count = len(original.deals[-1].events)
                if n >= len(match.deals) or count >= len(match.deals[n].events):
                    continue
                key = position_key(original.deals, n, count)
                if key != position_key(match.deals, n, count):
                    continue
                advice.setdefault(key, []).append({"record_id": record["record_id"],
                    "created_at": record.get("created_at"), "advice": record["advice"],
                    "source": record.get("context", {}).get("source", "dashboard")})
        except (ValueError, OSError, KeyError, TypeError):
            skipped += 1
    for records in advice.values():
        records.sort(key=lambda record: (record.get("created_at") or "", record["record_id"]))
    deals = []
    for number, deal in enumerate(match.deals):
        frames = []
        for index, event in enumerate(deal.events):
            if not isinstance(event, Play):
                continue
            before = replay_deal(deal.setup, deal.events[:index])
            after = replay_deal(deal.setup, deal.events[:index + 1])
            key = position_key(match.deals, number, index)
            completed = len(after.completed_tricks) > len(before.completed_tricks)
            trick = after.completed_tricks[-1] if completed else after.current_trick
            frames.append({"key": key, "event_index": index, "trick_number": len(before.completed_tricks) + 1,
                "played": event_data(event), "hand_before": [str(c) for c in sorted(before.hand, key=lambda c: c.id)],
                "legal_cards": list(map(str, before.legal_actions)),
                "trick": trick_data(trick, deal.setup.trump, complete=completed),
                "trick_complete": completed, "trick_points": after.trick_points,
                "position": {"trick": trick_data(before.current_trick, deal.setup.trump),
                    "next_player": int(before.next_player), "trick_points": before.trick_points,
                    "trick_counts": before.trick_counts, "remaining_counts": before.remaining_counts,
                    "awarded_melds": before.awarded_melds,
                    "revealed": [[str(c) for c in sorted(cs, key=lambda c: c.id)] for cs in before.revealed],
                    "events": [event_data(e) for e in deal.events[:index]],
                    "can_analyse": before.next_player == deal.setup.player},
                "advice": advice.get(key, []), "feedback": notes.get(key, {
                    "version": 0, "flagged": False, "alternative": "", "note": ""})})
        result = deal.state.result
        deals.append({"number": number + 1, "setup": setup_data(deal.setup),
            "phase": deal.state.phase.value, "score": deal.state.score,
            "recorded": getattr(result, "recorded", None),
            "earned": getattr(result, "earned", None), "frames": frames})
    return {"match_id": match.id, "revision": match.revision, "name": match.name,
            "deals": deals, "unreadable_logs": skipped}


def save_feedback(match, storage, payload):
    key = payload.get("key")
    positions = {position_key(match.deals, n, i): (d, i)
                 for n, d in enumerate(match.deals) for i, e in enumerate(d.events)
                 if isinstance(e, Play)}
    if not isinstance(key, str) or key not in positions:
        raise ValueError("This review position is no longer in the match. Reload the review.")
    flagged, alternative, note = (payload.get(k) for k in ("flagged", "alternative", "note"))
    if type(flagged) is not bool or not isinstance(note, str) or len(note) > 4000 or not isinstance(alternative, str):
        raise ValueError("Expected a flag, an alternative card and a note of at most 4000 characters.")
    deal, index = positions[key]
    before = replay_deal(deal.setup, deal.events[:index])
    if alternative and alternative not in list(map(str, before.legal_actions)):
        raise ValueError("The alternative must be one of your legal cards at this position.")
    notes = read_feedback(storage, match.id)
    version = notes.get(key, {}).get("version", 0)
    if type(payload.get("version")) is not int or payload["version"] != version:
        raise ValueError("This note changed in another window. Reload the review before saving.")
    feedback = {"version": version + 1, "flagged": flagged, "alternative": alternative, "note": note}
    notes[key] = feedback
    write_archive_text(storage / "review" / f"{match.id}.json", json.dumps(notes, ensure_ascii=False))
    return {"key": key, "feedback": feedback}

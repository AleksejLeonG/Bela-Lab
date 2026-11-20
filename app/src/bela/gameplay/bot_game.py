"""Interactive human-versus-bots controller with a separate private checkpoint.

Only public_view and the player archive may leave the controller. Policies use
observe(), never another seat's private hand. Six-card calling precedes pickup.
"""
from dataclasses import dataclass, replace
import json
from random import Random
from uuid import uuid4

from bela.analysis.policies import POLICIES, choose_move, announce_bela
from bela.analysis.trump import advise_trump
from bela.domain.cards import Card, Suit
from bela.domain.game import Seat
from bela.gameplay.batch import dealt_hands, derived_seed, tracked_observation
from bela.gameplay.calling import CallingState, CallingObservation
from bela.gameplay.session import MatchSession
from bela.gameplay.simulation import start_play, resolve_declarations, observe, play_card, declare_belot
from bela.gameplay.tracking import UserMatch, AddEvent, Play, NextDeal, DealSetup, Belot
from bela.rules.melds import has_belot
from bela.storage.persistence import dumps_match, loads_match
from bela.storage.user_storage import dumps_user_match, loads_user_match


@dataclass(frozen=True)
class BotGame:
    id: str
    name: str
    seed: int
    profiles: tuple
    revision: int = 0
    calling: CallingState | None = None
    session: MatchSession | None = None
    tracked: UserMatch | None = None
    awaiting_trick: bool = False
    declarations_pending: bool = False

    @classmethod
    def new(cls, name="Practice match", profile="mixed"):
        if not isinstance(name, str) or not name.strip() or len(name)>200:
            raise ValueError("Match name must contain 1–200 characters.")
        if profile not in ("mixed", *POLICIES):
            raise ValueError("Unknown bot strategy.")
        seed=Random().getrandbits(63)
        rng=Random(derived_seed(seed,"profiles"))
        profiles=tuple(rng.choice(POLICIES) if profile=="mixed" else profile for _ in range(4))
        return cls(str(uuid4()),name.strip(),seed,profiles,calling=CallingState(Seat.THREE))

    @property
    def deal_index(self):
        return len(self.session.deals) if self.calling is not None and self.session else max(0,len(self.session.deals)-1) if self.session else 0

    @property
    def hands(self):
        return dealt_hands(self.seed,self.deal_index)

    def advance_calling(self):
        if self.calling.next_player is None:
            return replace(self.begin_play(),revision=self.revision+1)
        player=self.calling.next_player
        if player==Seat.ZERO:
            raise ValueError("It is your calling turn.")
        advice=advise_trump(CallingObservation(player,tuple(self.hands[player][:6]),self.calling))
        calling=self.calling.pass_turn(player) if advice.action is None else self.calling.call_trump(player,advice.action)
        return replace(self,calling=calling,revision=self.revision+1)

    def call(self, suit):
        if self.calling is None or self.calling.next_player!=Seat.ZERO:
            raise ValueError("It is not your calling turn.")
        calling=self.calling.pass_turn(Seat.ZERO) if suit is None else self.calling.call_trump(Seat.ZERO,Suit(suit))
        return replace(self,calling=calling,revision=self.revision+1)

    def begin_play(self):
        calling=self.calling
        full=start_play(self.hands,trump=calling.trump,dealer=calling.dealer,caller=calling.caller,
            match_score=self.session.score if self.session else (0,0))
        belot=next((s for s in Seat if has_belot(full.hands[s])),None)
        if belot is not None:
            full=declare_belot(full,belot)
            setup=DealSetup(Seat.ZERO,tuple(self.hands[0]),full.dealer,full.caller,full.trump,full.match_score)
            fresh=replace(UserMatch.start(setup,self.name),id=self.id).perform(AddEvent(Belot(belot,tuple(full.hands[belot]))))
        else:
            full=resolve_declarations(full)
            fresh=replace(tracked_observation(full,Seat.ZERO,self.hands[0],self.id),name=self.name)
        if self.session:
            session=self.session.next_deal(self.hands,trump=calling.trump,caller=calling.caller).with_current(full)
            tracked=replace(self.tracked,commands=self.tracked.commands+(NextDeal(fresh.initial),)+fresh.commands)
            # Materialize now so invalid projections cannot reach persistence.
            tracked.state
        else:
            session=replace(MatchSession.start(full,name=self.name),id=self.id)
            tracked=fresh
        return replace(self,session=session,tracked=tracked,calling=None,awaiting_trick=False,declarations_pending=belot is None)

    def play(self, code):
        if self.calling is not None or self.declarations_pending or self.awaiting_trick or self.session.current.next_player!=Seat.ZERO:
            raise ValueError("Wait for your turn before playing a card.")
        card=Card.parse(code)
        return self._play(card,announce_bela(observe(self.session.current,Seat.ZERO),card))

    def _play(self, card, bela):
        old=self.session.current
        full=play_card(old,old.next_player,card,announce_bela=bela)
        tracked=self.tracked.perform(AddEvent(Play(old.next_player,card,bela)))
        return replace(self,session=self.session.with_current(full),tracked=tracked,
            awaiting_trick=len(full.completed_tricks)>len(old.completed_tricks),revision=self.revision+1)

    def step(self):
        if self.calling is not None:
            return self.advance_calling()
        if self.declarations_pending:
            return replace(self,declarations_pending=False,revision=self.revision+1)
        if self.awaiting_trick:
            return replace(self,awaiting_trick=False,revision=self.revision+1)
        full=self.session.current
        if full.finished or full.next_player==Seat.ZERO:
            raise ValueError("There is no bot waiting to play.")
        player=full.next_player
        move=choose_move(observe(full,player),Random(derived_seed(self.seed,"move",self.deal_index,
            sum(len(t.cards) for t in full.completed_tricks)+len(full.current_trick.cards))),self.profiles[player])
        return self._play(move.card,move.bela)

    def next_deal(self):
        if self.calling is not None or not self.session.current.finished or self.session.winner is not None:
            raise ValueError("Finish this deal before starting the next.")
        return replace(self,calling=CallingState(self.session.current.dealer.next),
            awaiting_trick=False,declarations_pending=False,revision=self.revision+1)

    def public_view(self):
        data={"id":self.id,"revision":self.revision,"name":self.name,"calling":self.calling is not None,
            "awaiting_trick":self.awaiting_trick,"human":0,"declarations_pending":self.declarations_pending}
        if self.calling is not None:
            advice=advise_trump(CallingObservation(Seat.ZERO,tuple(self.hands[0][:6]),self.calling)) if self.calling.next_player==Seat.ZERO else None
            data.update(hand=list(map(str,self.hands[0][:6])),dealer=int(self.calling.dealer),
                passes=list(map(int,self.calling.passes)),forced=self.calling.forced,
                calling_player=None if self.calling.next_player is None else int(self.calling.next_player),
                caller=None if self.calling.caller is None else int(self.calling.caller),
                trump=None if self.calling.trump is None else self.calling.trump.value,
                position=len(self.calling.passes)+1,
                suggestion=None if advice is None or advice.action is None else advice.action.value,
                rankings=[] if advice is None else [{"suit":r.suit.value,"score":r.score} for r in advice.rankings],
                score=list(self.session.score) if self.session else [0,0])
        elif self.session.current.meld_contest is not None:
            contest=self.session.current.meld_contest
            data["declarations"]={"winning_team":contest.winning_team,"winning_player":None if contest.winning_player is None else int(contest.winning_player),
                "presence":[{"player":int(p),"has_meld":has} for p,has in contest.presence],
                "reveals":[{"player":int(reveal.player),"melds":[{"kind":m.kind.value,"points":m.points,"high":m.high_rank.value,"cards":list(map(str,m.cards))} for m in reveal.melds]} for reveal in contest.revealed]}
        return data

    def dumps(self):
        return json.dumps({"format":"bela-private-bot-game-v1","id":self.id,"name":self.name,
            "seed":self.seed,"profiles":self.profiles,"revision":self.revision,
            "awaiting_trick":self.awaiting_trick,
            "declarations_pending":self.declarations_pending,
            "calling":None if self.calling is None else {"dealer":int(self.calling.dealer),"passes":list(map(int,self.calling.passes)),
                "caller":None if self.calling.caller is None else int(self.calling.caller),"trump":None if self.calling.trump is None else self.calling.trump.value},
            "session":None if self.session is None else json.loads(dumps_match(self.session)),
            "tracked":None if self.tracked is None else json.loads(dumps_user_match(self.tracked))})

    @classmethod
    def loads(cls,text):
        d=json.loads(text)
        if d.get("format")!="bela-private-bot-game-v1":raise ValueError("Unknown bot save format.")
        c=d["calling"]
        game=cls(d["id"],d["name"],d["seed"],tuple(d["profiles"]),d["revision"],
            None if c is None else CallingState(Seat(c["dealer"]),tuple(Seat(p) for p in c["passes"]),
                None if c.get("caller") is None else Seat(c["caller"]),None if c.get("trump") is None else Suit(c["trump"])),
            None if d["session"] is None else loads_match(json.dumps(d["session"])),
            None if d["tracked"] is None else loads_user_match(json.dumps(d["tracked"])),d["awaiting_trick"],d.get("declarations_pending",False))
        if game.session and (game.session.id!=game.id or game.tracked.id!=game.id):
            raise ValueError("Bot save identities disagree.")
        return game

import unittest

from bela.interfaces.localization import translate
from bela.domain.game import Seat
from bela.gameplay.tracking import FinishDeclarations, Play, Presence
from bela.interfaces.player_cli import event_text, parse_event, parse_suit
from bela.domain.cards import Suit


class LocalizationTests(unittest.TestCase):
    def test_english_is_default_and_nested_errors_keep_context(self):
        message = "Revision 3: Event 2: Card H_A has already been played."
        self.assertEqual(translate(message), message)
        self.assertEqual(translate(message, "hr"),
                         "Izmjena 3: Unos 2: Karta H_A već je odigrana.")
        self.assertEqual(translate("Unknown diagnostic xyz", "hr"), "Unknown diagnostic xyz")

    def test_english_console_commands_roundtrip_and_croatian_still_works(self):
        for command in ("presence 1 yes", "presence 1 no", "meld 1 50", "high 1 K",
                        "reveal 1 S_7 S_8 S_9", "melds none", "melds 0",
                        "move 0 H_Q bela", "belot 0"):
            with self.subTest(command=command):
                event = parse_event(command.split(), None)
                self.assertEqual(parse_event(event_text(event).split(), None), event)
        self.assertEqual(parse_event("presence 1 yes".split(), None), Presence(Seat.ONE, True))
        self.assertEqual(parse_event("melds none".split(), None), FinishDeclarations(None))
        self.assertEqual(parse_event("move 0 H_Q bela".split(), None),
                         parse_event("potez 0 H_Q bela".split(), None))
        self.assertEqual(parse_suit("hearts"), Suit.HEARTS)

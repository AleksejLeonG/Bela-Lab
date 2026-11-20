"""Deck identity, numeric pip counts and self-contained vector assets."""
import unittest
from xml.etree import ElementTree as ET

from bela.interfaces.dashboard import CARD_ASSETS, WEB_ROOT


class CardArtTests(unittest.TestCase):
    def test_all_32_faces_are_standalone_vectors_with_correct_identities(self):
        files = list((WEB_ROOT / "cards/hungarian").glob("*.svg"))
        self.assertEqual(len(files), 32)
        ns = {"s": "http://www.w3.org/2000/svg"}
        for path in files:
            with self.subTest(card=path.stem):
                root = ET.parse(path).getroot()
                self.assertEqual(root.get("data-card"), path.stem)
                self.assertIn(f"/cards/hungarian/{path.name}", CARD_ASSETS)
                self.assertEqual(root.get("viewBox"), "0 0 180 280")
                self.assertIsNotNone(root.find("s:title", ns))
                self.assertIsNone(root.find(".//s:image", ns))
                self.assertIsNone(root.find(".//s:script", ns))
                for use in root.findall(".//s:use", ns):
                    self.assertEqual(use.get("href"), "#suit")
                rank = path.stem.split("_")[1]
                if rank.isdigit():
                    group = root.find(f'.//s:g[@data-pip-count="{rank}"]', ns)
                    self.assertEqual(len(group.findall(".//s:use", ns)), int(rank))

    def test_photo_asset_and_unrecognized_card_paths_are_not_served(self):
        self.assertNotIn("/cards/tell-deck.jpg", CARD_ASSETS)
        self.assertNotIn("/cards/hungarian/../../app.js", CARD_ASSETS)
        self.assertNotIn("/cards/hungarian/H_2.svg", CARD_ASSETS)
        self.assertFalse((WEB_ROOT / "cards/tell-deck.jpg").exists())



if __name__ == "__main__":
    unittest.main()

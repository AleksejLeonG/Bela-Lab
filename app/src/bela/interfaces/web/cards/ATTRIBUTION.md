# Bela Lab card artwork

## Traditional Hungarian deck

The default deck uses 32 digitally illustrated WebP faces in `hungarian-illustrated/`. The artwork
uses the traditional Hungarian (Tell) deck, with hearts, leaves, bells and acorns,
mirrored court figures, and seasonal aces. In the engine, H = hearts, S = leaves,
D = bells and C = acorns. Unter maps to J and Ober to Q. The aces depict spring
(hearts), summer (bells), autumn (leaves), and winter (acorns).

The project also includes 32 standalone SVG faces in `hungarian/` and four
standalone suit symbols. Regenerate the vector faces from the repository root:

    python app/tools/generate_hungarian_cards.py

The Standard option uses the standard rank-and-suit presentation.

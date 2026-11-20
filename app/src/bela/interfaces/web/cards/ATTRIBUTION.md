# Bela Lab card artwork

## Traditional Hungarian deck

Bela Lab uses 32 project-authored SVG faces in `hungarian/`. The artwork
uses the traditional Hungarian (Tell) deck, with hearts, leaves, bells and acorns,
mirrored court figures, and seasonal aces. In the engine, H = hearts, S = leaves,
D = bells and C = acorns. Unter maps to J and Ober to Q. The aces depict spring
(hearts), summer (bells), autumn (leaves), and winter (acorns).

Each card is a self-contained SVG. The four standalone suit symbols were also
drawn for the project. Regenerate the faces from the repository root:

    python app/tools/generate_hungarian_cards.py

The Standard option uses the standard rank-and-suit presentation.

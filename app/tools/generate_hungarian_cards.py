"""Generate Bela Lab's original, standalone Hungarian-inspired SVG deck.

Standard library only. Run from any directory; no photos, tracing, fonts,
network resources or third-party artwork are embedded in the cards.
"""
from pathlib import Path
from xml.etree import ElementTree
from hungarian_illustrations import court_half, season_half

OUTPUT = Path(__file__).resolve().parents[1] / "src/bela/interfaces/web/cards/hungarian"
RANKS = ("7", "8", "9", "10", "J", "Q", "K", "A")
PAPER, INK, GOLD = "#fffdf5", "#453a30", "#bd944a"
SUITS = {
    "H": ("Hearts", "#b8483f", "#3d7555", "Spring"),
    "S": ("Leaves", "#3b704b", "#b95c3f", "Autumn"),
    "D": ("Bells", "#b28a30", "#315f86", "Summer"),
    "C": ("Acorns", "#815a36", "#8f4140", "Winter"),
}


def suit_shape(suit):
    return {
        "H": '<path fill="#bb443b" stroke="#923c32" stroke-width=".7" d="M16 33C11 27 2 20 2 12 2 3 12 1 16 9 20 1 30 3 30 12 30 20 21 27 16 33Z"/><path fill="none" stroke="#e98a68" stroke-width="1.3" d="M7 12C7 8 10 7 12 9"/>',
        "S": '<path fill="#48774d" stroke="#2d5137" stroke-width="1" d="M14 31C-1 27 3 7 28 2 29 22 25 31 14 31Z"/><path fill="none" stroke="#c4ab51" stroke-width="1.2" d="M8 35 25 7M13 25 7 20M18 18 12 12M18 18 26 18"/>',
        "D": '<path fill="#dcb348" stroke="#8c6728" stroke-width="1" d="M16 3C27 3 30 12 28 25 20 30 12 30 4 25 2 12 5 3 16 3Z"/><path fill="#b64b3d" d="M4 17H28V22H4Z"/><path fill="#42714d" d="M4 22H28L26 27 22 25 18 28 14 25 10 28 6 26Z"/><path stroke="#896127" stroke-width="1.5" d="M16 4V11"/><circle cx="16" cy="32" r="2.4" fill="#896127"/>',
        "C": '<path fill="#d7ad4b" stroke="#855e31" stroke-width="1" d="M8 15H25C25 26 22 33 16 35 10 32 7 26 8 15Z"/><path fill="#b1483b" stroke="#80452f" stroke-width=".6" d="M9 16C9 4 23 2 24 16Z"/><path fill="#49734d" stroke="#35523b" stroke-width="1" d="M5 16H27L26 22 22 24 18 22 14 24 10 22 6 22Z"/><path stroke="#735334" stroke-width="1.6" fill="none" d="M16 6Q15 2 11 2"/>',
    }[suit]


def pip(x, y, size=29, inverted=False):
    rotation = ' rotate(180)' if inverted else ''
    return f'<g transform="translate({x} {y}){rotation}"><use href="#suit" x="{-size/2}" y="{-size*36/64}" width="{size}" height="{size*36/32}"/></g>'


def frame(suit, rank, body):
    name, color, _, _ = SUITS[suit]
    label = {"J": "Unter", "Q": "Ober", "K": "King", "A": "Ace"}.get(rank, rank)
    mark = {"7": "VII", "8": "VIII", "9": "IX", "10": "X", "J": "U", "Q": "O", "K": "K", "A": "A"}[rank]
    corner = f'<g fill="{color}" font-family="Georgia,serif" font-size="17" font-weight="bold" text-anchor="middle"><text x="18" y="25">{mark}</text></g>{pip(18,42,16)}'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 280" preserveAspectRatio="none" role="img" aria-labelledby="title" data-card="{suit}_{rank}">
<title id="title">{name} {label} — Bela Lab original Hungarian-inspired deck</title>
<defs><linearGradient id="skin" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#f4d2a6"/><stop offset=".55" stop-color="#e5b082"/><stop offset="1" stop-color="#bf835c"/></linearGradient><symbol id="suit" viewBox="0 0 32 36">{suit_shape(suit)}</symbol></defs>
<rect x="1" y="1" width="178" height="278" rx="10" fill="{PAPER}" stroke="#d5cab1" stroke-width="2"/>
<rect x="6" y="6" width="168" height="268" rx="7" fill="none" stroke="#e9dfc9" stroke-width=".7"/>
{corner}<g transform="translate(180 280) rotate(180)">{corner}</g>
{body}
</svg>'''


def number_card(rank):
    positions = {
        "7": [(x,y) for x in (49,131) for y in (67,140,213)] + [(90,140)],
        "8": [(x,y) for x in (49,131) for y in (61,112,168,219)],
        "9": [(x,y) for x in (48,90,132) for y in (65,140,215)],
        "10": [(x,y) for x in (48,132) for y in (57,106,174,223)] + [(90,99),(90,181)],
    }[rank]
    label = {"7":"VII", "8":"VIII", "9":"IX", "10":"X"}[rank]
    return f'<text x="90" y="29" text-anchor="middle" fill="{INK}" font-family="Georgia,serif" font-size="19">{label}</text><g data-pip-count="{rank}">' + ''.join(pip(x,y,29,y>140) for x,y in positions) + '</g>' + number_scene(rank)


def number_scene(rank):
    y = {"7": 103, "8": 140, "9": 103, "10": 140}[rank]
    scene = '<path d="M-26 7Q-8-4 3 4T28 7V11H-26Z" fill="#a8b78b" stroke="#75865a" stroke-width=".5"/>'
    if rank in ("7", "9"):
        scene += '<path d="M-16 5V-8h7V5M-3 5V-14H5V5M13 5V-6h7V5" fill="#dfc993" stroke="#806e47" stroke-width=".6"/><path d="M-18-8l6-5 5 5M-5-14l6-6 6 6M11-6l6-5 5 5" fill="#a46745" stroke="#806e47" stroke-width=".6"/><path d="M-9-2h6M5-2h8" stroke="#9c8556" stroke-width="3"/><path d="M-13-5v3M1-10v3M17-3v3" stroke="#615541" stroke-width="1"/>'
    else:
        scene += '<path d="M-25 9q17-7 29 0t23 0" fill="none" stroke="#9db8bc" stroke-width="2"/><path d="M-22 3Q0-15 23 3V8H17V3Q0-8-16 3V8H-22Z" fill="#d4bc8d" stroke="#82704e" stroke-width=".6"/><path d="M-17 0V-5M-9-5v-5M0-7v-5M9-5v-5M17 0v-5" stroke="#82704e" stroke-width=".6"/>'
    return f'<g transform="translate(90 {y})">{scene}</g>'


def court_card(suit, rank):
    half=court_half(suit,rank)
    return half+f'<g transform="translate(180 280) rotate(180)">{half}</g><path d="M39 140H141" stroke="{GOLD}" stroke-width="1.5"/>'


def ace_card(suit):
    half=season_half(suit)
    return half+f'<g transform="translate(180 280) rotate(180)">{half}</g><path d="M36 140H144" stroke="{GOLD}"/>'


def build():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    for suit in SUITS:
        for rank in RANKS:
            body=number_card(rank) if rank.isdigit() else ace_card(suit) if rank=="A" else court_card(suit,rank)
            text=frame(suit,rank,body)
            ElementTree.fromstring(text)
            (OUTPUT/f"{suit}_{rank}.svg").write_text(text+'\n',encoding='utf-8')
    print(f"Created 32 original SVG cards in {OUTPUT}")


if __name__ == "__main__":
    build()

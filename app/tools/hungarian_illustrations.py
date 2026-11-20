"""Original vector illustrations for Bela Lab's Hungarian-inspired deck.

Drawn from geometric paths, not traced or reconstructed from another deck.
Traditional suits, mirrored composition and seasonal aces are the conventions;
the costumes, faces, poses and scenery are original compositions.
"""

INK = "#493b30"
GOLD = "#c49b4a"
PALE = "#f2e4bc"
PALETTES = {
    "H": ("#a9463f", "#3b7059", "#563d2c"),
    "S": ("#3d6d56", "#bf8050", "#705239"),
    "D": ("#b88e36", "#3d6581", "#654839"),
    "C": ("#8a5940", "#854652", "#4b3a32"),
}


def path(d, fill="none", stroke=INK, width=.8, **attrs):
    extra=' '.join(f'{k.replace("_","-")}="{v}"' for k,v in attrs.items())
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round" {extra}/>'


def circle(x,y,r,fill,stroke="none",width=.5):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'


def flower(x,y,size=4,color="#bf6261"):
    petals=''.join(f'<ellipse cx="{x}" cy="{y-size*.65}" rx="{size*.35}" ry="{size*.65}" transform="rotate({i*72} {x} {y})" fill="{color}" stroke="#87503b" stroke-width=".3"/>' for i in range(5))
    return petals+circle(x,y,size*.28,"#dec45f")


def embroidery(x1,x2,y):
    out=path(f'M{x1} {y-3}H{x2}M{x1} {y+3}H{x2}',stroke="#dfbc69",width=.65)
    for x in range(int(x1)+3,int(x2),7):
        out+=path(f'M{x} {y-2}l2 2-2 2-2-2Z',"#e7c67b",stroke="#81602d",width=.35)
    return out


def face(hair, older=False):
    out=path('M77 46Q74 36 84 32Q99 28 107 42L107 58Q103 70 91 73Q81 71 77 62Z',hair)
    out+=path('M80 43Q90 35 101 43L102 51 106 57 102 59 101 65Q95 72 87 67L81 61Z',"url(#skin)")
    out+=path('M79 48Q74 45 75 52Q76 58 82 57',"#e9b98a")
    out+=path('M78 49q-2 0-1 4M84 47q3-3 7-1M96 45q3-2 5 0',stroke=hair,width=.9)
    out+=path('M85 50q3-2 6 0M96 49q3-2 5 0',stroke=INK,width=.65)
    out+=circle(88,50,1,INK)+circle(99,49,.9,INK)
    out+=path('M94 50l-1 8 4 1M87 62q5-2 10 0M88 65q4 2 7 0',stroke="#9e674c",width=.7)
    out+=path('M86 60q5-4 8 0 3-5 7-1l-2 4-5-1-4 2Z',hair,stroke=hair,width=.4)
    if older:
        out+=path('M81 61q4 4 10 4 8 1 12-4l-2 14-12 13-7-13Z',"#d4cbb0",width=.6)
        out+=path('M84 67l3 10M90 69v12M96 68l-3 12M83 56l5 1M97 54l4 1',stroke="#948570",width=.55)
    else:
        out+=path('M77 43q-5 6 1 14M79 39q6-6 11-4M99 36q8 4 6 12',stroke="#9f8257",width=.6)
    return out


def court_half(suit,rank):
    coat,lining,hair=PALETTES[suit]
    out=path('M67 72Q48 75 42 93L37 138H143L137 93Q130 78 111 73Z',lining,width=1.1)
    out+=path('M57 84Q70 75 78 76L85 137H43Q44 108 57 84Z',coat,width=.7)
    out+=path('M112 77Q129 80 135 94L142 137H101Z',coat,width=.7)
    out+=path('M76 75Q91 70 109 76L115 138H64Z',coat,width=1)
    out+=path('M84 77Q89 83 95 82L100 138H78Z',"#d9b35e",width=.7)
    out+=path('M80 74 91 83 102 74 100 69H84Z',"#f5e9ca",width=.7)
    for x in (82,85,98,101):out+=path(f'M{x} 75l3 7',stroke="#ad9b77",width=.45)
    out+=path('M72 85Q63 102 65 127M109 85q8 15 4 41M50 98q5 10-4 28M132 99q-4 12 3 27',stroke="#352b24",width=.55,opacity=".55")
    out+=path('M70 90Q73 103 69 114M105 89q-2 14 4 26M52 94l-3 18M125 94l5 19',stroke="#e5c48a",width=.65,opacity=".75")
    for y in (89,98,107,116,125):
        out+=circle(90,y,1.7,"#e7c56b",INK,.35)
        out+=path(f'M84 {y}q6-3 12 0',stroke="#876331",width=.5)
    out+=embroidery(64,113,130)
    for x in (71,105):
        for y in (91,109):out+=flower(x,y,2.1,"#dfb96a")
    out+=face(hair,rank=="K")
    if rank=="J":
        # A hooded ranger with a diagonal crossbow; not a commercial Tell figure.
        out+=path('M72 43Q68 28 83 25Q101 22 110 38L104 42Q95 30 82 37L78 47Z',lining,width=1)
        out+=path('M72 42Q89 32 107 41L111 46Q94 40 77 48Z',coat,width=.8)
        out+=path('M78 29q12-4 22 3M76 35q13-4 25 2',stroke="#d1b17b",width=.5)
        out+=path('M52 82Q42 85 45 98L69 113 81 106 58 91Z',lining,width=1)
        out+=path('M120 87q12 2 9 14l-24 9-7-8 22-15Z',lining,width=1)
        out+=embroidery(51,64,97)
        out+=path('M57 119 128 83 132 88 67 127Z',"#a97c44",width=.9)
        out+=path('M67 96Q84 73 112 98',stroke=INK,width=2)
        out+=path('M67 96 112 98',stroke="#987d52",width=.6)
        out+=path('M73 113 106 97M78 117 110 101',stroke="#ead195",width=.55)
        out+=path('M71 103q8-5 14-1l4 5-5 7-10-4Z',"url(#skin)",width=.75)
        out+=path('M104 98q5-3 9 0l-1 7-9 3-4-4Z',"url(#skin)",width=.75)
        out+=path('M76 104l6 5M79 102l6 5M104 100l6 2',stroke="#a16e50",width=.5)
        out+=path('M62 119 72 124 69 132 59 127Z',lining,width=.7)
    elif rank=="Q":
        # Ober: feathered herald with an unfurled scroll and a narrow staff.
        out+=path('M72 42Q72 25 92 25Q108 25 112 38L103 43Z',lining,width=1)
        out+=path('M70 43Q91 34 113 41L110 47Q92 42 73 49Z',coat,width=.9)
        out+=path('M101 30Q111 10 127 19 118 20 111 34Z',"#d8bd77",width=.7)
        out+=path('M107 29 122 20M110 25l2-5M114 25l7-1',stroke="#8e774e",width=.5)
        out+=path('M125 38 122 138',stroke=INK,width=3)
        out+=path('M125 38 122 138',stroke="#c5a55a",width=1.5)
        out+=path('M123 40q-6-7 2-10 8 5 2 10Z',"#c5a55a",width=.65)
        out+=path('M53 83Q42 87 48 101L76 117 81 108 60 91Z',lining,width=1)
        out+=path('M116 82q13 4 11 15l-16 11-7-8 12-18Z',lining,width=1)
        out+=path('M72 98Q91 94 110 104L105 123Q90 113 70 118L75 103Q68 105 68 101Z',"#f2dfad",width=.8)
        out+=path('M80 104q10-1 20 4M79 109q10-1 19 4M78 113l10 2',stroke="#9d8255",width=.55)
        out+=path('M71 108q8-3 12 1l-1 6-8 3-6-5Z',"url(#skin)",width=.7)
        out+=path('M108 99q8-4 11 2l-1 8-8 2-5-6Z',"url(#skin)",width=.7)
        out+=path('M73 110l6 3M111 102l5 2M110 105l5 2',stroke="#a16e50",width=.5)
    else:
        # King: an ermine-edged regent with an orb, jewel crown and dress sword.
        out+=path('M75 40 71 24 80 29 84 19 91 28 99 18 103 29 112 24 107 41Z',"#d2ac55",width=.9)
        out+=path('M75 36Q91 32 108 36L107 43Q92 38 76 43Z',lining,width=.7)
        for x,y in ((80,33),(92,32),(104,33)):out+=circle(x,y,1.9,coat,"#f0d58b",.5)
        out+=path('M58 78Q68 72 78 75L70 138H55Q64 103 58 78Z',"#e6dec7",width=.8)
        out+=path('M106 75Q117 74 125 82L136 138H122Z',"#e6dec7",width=.8)
        for x,y in ((64,85),(65,98),(62,111),(60,124),(117,88),(121,102),(125,118)):
            out+=path(f'M{x} {y}l-1 4 3-1-1-3Z',"#4a4135",stroke="none")
        out+=path('M49 93Q44 103 62 115L79 111 74 103 59 102Z',coat,width=.9)
        out+=path('M117 92q14 6 10 18l-23 5-3-10Z',coat,width=.9)
        out+=circle(115,102,11,"#c9a14f",INK,.8)
        out+=path('M105 102q10-9 20 0M115 91v22',stroke="#f1d991",width=.9)
        out+=path('M115 91V81M111 85h8',stroke=INK,width=1.5)
        out+=path('M105 111q10-5 15 0l-2 6-12 1-5-4Z',"url(#skin)",width=.7)
        out+=path('M49 120 100 84 103 88 55 128Z',"#dce0d7",width=.8)
        out+=path('M53 115 61 128M48 125 57 134',stroke="#a58748",width=2)
        out+=path('M67 106q6-4 11 0l2 6-10 4-6-5Z',"url(#skin)",width=.7)
    # The suit on an Ober is high, on an Unter low: recognition without labels.
    out+=f'<use href="#suit" x="35" y="{45 if rank=="Q" else 82 if rank=="J" else 46}" width="22" height="25"/>'
    out+=embroidery(43,139,137)
    return out


def season_half(suit):
    coat,accent,hair=PALETTES[suit]
    season={"H":"SPRING","D":"SUMMER","S":"AUTUMN","C":"WINTER"}[suit]
    out=f'<text x="90" y="40" fill="{INK}" text-anchor="middle" font-family="Georgia,serif" font-size="9" letter-spacing="1">{season}</text>'
    out+=path('M37 76Q58 61 83 72T144 70V139H37Z',"#e1e7d2",stroke="none")
    out+=path('M37 103Q62 84 88 97T144 91V139H37Z',"#a9bc8d",stroke="none")
    out+=path('M37 119Q81 107 144 115V139H37Z',"#799061",stroke="none")
    out+=path('M39 129q30-9 54-3M100 132q20-7 41-3',stroke="#c0be83",width=.7)
    # Small distant farmhouse, kept behind the figure.
    out+=path('M119 85V70h17v15Z',"#e5d4a5",width=.55)
    out+=path('M116 71 127 62 140 71Z',"#a75a42",width=.65)
    out+=path('M124 85V77h5v8M132 74h2v3',stroke="#665c43",width=.75)
    if suit=="C":
        out+=path('M37 101 57 78 82 100 109 74 144 101V139H37Z',"#cbd9d8",stroke="none")
        out+=path('M37 120Q81 107 144 116V139H37Z',"#f0ebdd",stroke="none")
        out+=path('M44 117V76M44 79l-8 14h16M44 87l-11 17h22M44 97l-13 17h26',"#55735e",stroke="#48624e",width=.6)
    elif suit=="H":
        out+=path('M46 116V61M45 79 34 66M46 87l16-18',stroke="#806140",width=2)
        for x,y in ((36,65),(44,58),(55,62),(61,70),(37,78)):
            out+=flower(x,y,2.8,"#d5a9a3")
    elif suit=="S":
        out+=path('M46 117V60M46 72 35 62M46 84l18-19M46 97 34 89',stroke="#806140",width=2)
        for x,y in ((35,63),(43,56),(57,63),(62,70),(37,84)):
            out+=path(f'M{x} {y}q-7-8 1-12 8 5 1 12Z',"#b78440",width=.3)
    # Original seasonal portrait in a flowing regional costume.
    out+=path('M79 89Q89 81 102 89L116 137H63Z',coat,width=.9)
    out+=path('M82 90 90 98 98 90 102 137H76Z',accent,width=.6)
    out+=path('M76 95Q69 94 65 108L52 116 56 121 75 111 82 102Z',"#ebdebe",width=.8)
    out+=path('M103 95q10-4 14 8l8 9-5 5-16-13Z',"#ebdebe",width=.8)
    out+=path('M78 110Q77 124 70 136M106 111l5 25M85 112l-2 23M95 112l3 23',stroke="#d7ad72",width=.65)
    out+=embroidery(72,108,130)
    out+=path('M80 69Q81 56 91 56 104 56 104 73L101 84 93 89 83 82Z',hair,width=.8)
    out+=path('M83 68Q93 62 100 68L101 79Q96 88 88 81Z',"url(#skin)",width=.65)
    out+=path('M86 72h3M96 72h2M93 73l-1 5h3M89 81q4 2 7-1',stroke="#855b46",width=.65)
    out+=path('M80 67Q88 54 102 66M82 62q8-8 16-1',stroke="#b08c56",width=.7)
    if suit=="H":
        for x,y in ((82,64),(87,60),(94,60),(101,64)):out+=flower(x,y,1.8,"#d6b8aa")
        for x,y in ((48,130),(57,127),(124,126),(132,133)):
            out+=path(f'M{x} 138V{y}',stroke="#426a40",width=.9)+flower(x,y,2.7)
        out+=path('M54 117q-4-3-7 1l2 5 7-1Z',"url(#skin)",width=.6)
    elif suit=="D":
        out+=path('M79 64Q90 49 105 64Z',"#d1ac5f",width=.6)+path('M76 65H108',stroke="#99713b",width=2)
        for x in (122,127,132):
            out+=path(f'M{x} 137V99m0 12-4-4m4-1 4-4m-4-1-3-4',stroke="#bd9641",width=1.1)
        out+=path('M121 114q5-4 9-1l-1 6-7 2Z',"url(#skin)",width=.6)
    elif suit=="S":
        out+=path('M119 121q3-7 15-3l2 19h-18Z',"#ac8251",width=.7)
        out+=path('M119 124q9 3 17 0M119 128q9 3 17 0M120 132q8 3 16 0',stroke="#795d3e",width=.45)
        for x,y in ((123,117),(129,115),(134,119),(127,121)):
            out+=circle(x,y,2.6,"#725a78",INK,.3)
    else:
        out+=path('M82 81q10 3 20-1l-5 13-10 2Z',"#ddd5bf",width=.5)
        out+=path('M80 69Q77 59 89 55L103 64 99 69Z',accent,width=.6)
        out+=path('M119 135q-6-8 2-14-1 7 4 6l3-12q11 11 3 20Z',"#bd5b38",width=.7)
        out+=path('M122 135q-2-6 3-9l1 4 3-2 1 7Z',"#e2b75a",stroke="none")
        out+=path('M115 138 137 133M116 133l21 5',stroke="#73533b",width=2)
    out+=f'<use href="#suit" x="35" y="44" width="22" height="25"/>'
    return out

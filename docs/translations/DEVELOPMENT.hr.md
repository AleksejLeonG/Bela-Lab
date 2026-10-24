# Bela Engine

Python engine za dogovorenu hrvatsku belu za četiri igrača. Početni kostur radi lokalno, bez vanjskih servisa i bez dodatnih izvršnih ovisnosti. Potreban je Python 3.11 ili noviji.

## Vizualni dashboard

Na Windowsu dvaput klikni **START_BELA.cmd** ili pokreni `python app/run.py`. Lokalni preglednik prikazuje stol, izbor karata, javna zvanja, povijest s ispravcima i spremljene partije. Pravila provjerava isti Python engine; sučelje ne zna tuđe neotkrivene karte. Za prvu probu klikni **Isprobaj primjer**.

[Upute i arhitektura dashboarda](DASHBOARD.hr.md) opisuju rad, spremanje i API za daljnji razvoj. Tekstualni način u nastavku i dalje ostaje dostupan.

## Unos vlastite stvarne igre

Glavni pokretač otvara dashboard. Za tekstualni način iz terminala pokreni `.\START_BELA.cmd --text` ili:

```powershell
python app/run.py --text
```

Pokretač pita za tvoju ruku i podatke partije. Zatim unosiš javna zvanja i poteze, vidiš svoje legalne karte, ispravljaš pogreške i automatski spremaš partiju. Tuđe nepokazane ruke ostaju nepoznate. [Detaljne upute i naredbe](USER_GUIDE.hr.md) objašnjavaju unos, nastavak i granice provjere. Za brzu probu koristi `python app/run.py --text --load examples/player_match.json --save saves/isprobavanje.player.json`.

Raniji `python -m bela` ostaje razvojni simulator s četiri poznate ruke. Novi korisnički način dostupan je i kao `python -m bela track`.

## Pokretanje

Iz projektnog foldera, u PowerShellu:

```powershell
$env:PYTHONPATH = "$PWD\app\src"
python -m bela --seed 42
python -m unittest discover -s app/tests -v
```

Naredba `python` treba upućivati na odabrani Python interpreter. Alternativno, za razvojnu instalaciju u vlastitom virtualnom okruženju:

```powershell
python -m venv app/.venv
.\app\.venv\Scripts\python.exe -m pip install -e ./app
.\app\.venv\Scripts\python.exe -m bela
```

Razvojna instalacija može trebati pristup repozitoriju paketa za build alat. Pokretanje preko `PYTHONPATH` ne zahtijeva instaliranje paketa.

## Što već radi

- Svih 32 karte, stabilne oznake, mjesta igrača i parovi.
- Jačina i vrijednost karata te pobjednik štiha.
- Praćenje boje, iber, obvezno adutiranje i nadjačavanje aduta, uključujući kada partner nosi.
- Nepromjenjivo potpuno stanje simulatora i odvojeni pogled pojedinog igrača.
- Odigravanje osam štihova uz provjeru redoslijeda i legalnosti.
- Prepoznavanje četiriju jednakih karata i maksimalnih nizova, bez dvostrukog računanja podnizova.
- Usporedba najjačih zvanja, prednost mjesta kod izjednačenja i zbroj svih zvanja pobjedničkog para.
- Odvojena evidencija izgovorenih vrijednosti, završnih karata nizova i pokazanih zvanja. Gubitničke nepokazane karte ostaju skrivene.
- Najava bele uz prvi odigrani adutski K ili Q; propuštena ili ponovljena najava odbija se.
- Belot kao trenutačna pobjeda u partiji, uz pokazivanje karata i bez izmišljenog bodovnog upisa.
- Obračun karata, zadnjeg štiha, štiglje i pada te provjera završetka partije.
- Simulator automatski prenosi utvrđena zvanja i najavljenu belu u obračun; par bez štiha ostaje bez tih bodova.
- Spremanje i učitavanje cijele partije u verzionirani JSON, uključujući završena dijeljenja i nedovršeni štih.
- Nastavak nakon učitavanja, očuvanje izgovorenih najava i provjera zapisa ponovnim legalnim odigravanjem povijesti.
- Sigurna zamjena prethodne datoteke tek nakon što je novi zapis potpuno napisan.

## Granice ovog kostura

Simulator i korisnički unos počinju nakon odabira aduta i podizanja talona, u fazi zvanja. Zvanje aduta, talon prije zvanja i statistički savjeti još nisu implementirani. Stvarna igra ima tekstualno i početno vizualno sučelje s nepoznatim tuđim rukama, ispravcima i zasebnim formatom spremanja.

Razvojni primjer razrješava istinita zvanja iz potpuno poznatih ruku simulatora, pokazuje pobjednička zvanja te najavljuje belu kad prvi put odigra pripadajuću kartu. Dodatne izgovorene usporedbe upisuju se posebno; sustav ih ne izmišlja i ne otkriva sve gubitničke kombinacije. Puni redoslijed interaktivnih pitanja i odgovora pripada budućem modulu sesije. Namjerno se još ne modelira prešućivanje zvanja ili nepravilno igranje.

Savjetnik trenutno vraća samo legalne karte, u stabilnom redoslijedu oznaka. Nema statističkog rangiranja ni procjene vjerojatnosti. Potpuno stanje simulatora ne predaje se savjetniku.

## Spremanje razvojnog simulatora

Iz projektnog foldera, nakon postavljanja `PYTHONPATH` kao iznad:

```powershell
# Odigraj pet pojedinačnih poteza i spremi poziciju usred drugog štiha.
python -m bela --moves 5 --name "Moja partija" --save saves/moja_partija.json

# Učitaj, odigraj još tri poteza i spremi u istu datoteku.
python -m bela --load saves/moja_partija.json --moves 3 --save saves/moja_partija.json

# Učitaj i dovrši trenutačno dijeljenje razvojnim načinom igranja.
python -m bela --load saves/moja_partija.json --save saves/moja_partija.json

# Započni sljedeće razvojno dijeljenje i spremi ga prije objave zvanja.
python -m bela --load saves/moja_partija.json --next-deal --seed 43 --moves 0 --save saves/moja_partija.json
```

`--moves` broji pojedinačne odigrane karte, ne štihove. Bez te opcije razvojni primjer dovršava dijeljenje. `--moves 0` čuva točno početnu ili učitanu fazu bez daljnjeg igranja. `--load` sam po sebi ne mijenja izvornu datoteku; za upis nastavka treba i `--save`. Postojeći cilj `--save` zamjenjuje se novim valjanim zapisom. Ovo je automatizirani razvojni primjer, a ne interaktivni unos vlastitih poteza.

`--next-deal` zahtijeva završeno prethodno dijeljenje i partiju koja još nema pobjednika. Bodovi se prenose jednom, djelitelj se pomiče, a povijest ostaje sačuvana. Novi adut i zvatelj u razvojnom primjeru i dalje su herc i igrač 0; biblioteka omogućuje njihovo zadavanje. Pri običnom učitavanju ostaju sačuvani izvorni adut, zvatelj, djelitelj i ruke; `--seed` služi samo za novo razvojno dijeljenje.

Zapis sadrži identitet i naziv partije, verziju formata i pravila, početne karte svakog dijeljenja te akcije potrebne za rekonstrukciju. Bodovi i javno pokazana zvanja izračunavaju se ponovno. Nelegalni potezi, proturječni podaci, nepodržane verzije i oštećeni zapisi odbijaju se; ne vraćamo djelomično učitanu partiju.

To je za sada **potpuni zapis simulatora sa sve četiri ruke**, a ne javni izvoz ili zapis buduće aplikacije koja zna samo našu ruku. Učitani zapis ne predaje se izravno savjetniku; i dalje se koristi `observe(state, player)`. Format ima granicu 8 MiB i najviše 1000 dijeljenja. Spremanje nije sinkronizacija između uređaja niti rješavanje istodobnih izmjena iste datoteke.

Primjer spremljene nedovršene partije nalazi se u [examples/simulator_match.json](../../examples/simulator_match.json).

Biblioteka izlaže `MatchSession.start(state)`, `session.with_current(new_state)`, `session.next_deal(...)`, `save_match(session, path)` i `load_match(path)`. `session.score` vraća aktualan obračunati rezultat, a `session.winner` pobjednički par ili `None`. Za belot se pobjeda čuva zasebno, bez dodavanja fiktivnih bodova. Funkcije su u modulima `bela.gameplay.session` i `bela.storage.persistence`.

## Početni dizajn

```text
domain/         Karte, mjesta, zvanja, faze, stanje i pogled igrača
rules/          Čiste funkcije za legalnost, zvanja i obračun
simulation.py   Faza zvanja, bela, belot i prijelaz nakon poteza
session.py      Povijest dijeljenja, ukupan rezultat i nastavak partije
persistence.py  Verzionirani JSON, provjera ponovnim odigravanjem i spremanje
tracking.py     Vlastita ruka, javni događaji, provjera skrivenih raspodjela i ispravci
user_storage.py Korisnički zapis bez izmišljenih protivničkih ruku
user_cli.py     Tekstualni unos i automatsko spremanje stvarne partije
dashboard.py    Lokalni HTTP API i upravljanje otvorenom partijom
web/            Početno vizualno sučelje za preglednik
advisor.py      Sučelje koje prima samo pogled igrača
cli.py          Pokretljiv razvojni primjer
tests/          Rubni slučajevi pravila i cjelovita odigravanja
```

Pravila nemaju ovisnost o simulatoru, analizi ili budućem web sučelju. Prijelaz vraća novo stanje pa se staro može sačuvati za usporedbu i buduću povijest događaja. `PlayState` stvara se kroz `start_play`; izravna konstrukcija interni je detalj i nije uvoz nepouzdanih korisničkih podataka.

Niskorazinska funkcija obračuna prima već potvrđene podatke; simulator provjerava zvanja iz početnih ruku i pravodobnost bele na samom potezu. Javni ulaz buduće aplikacije proći će zasebnu provjeru formata, faza i povijesti.

## Korištenje novih pravila

`start_play(...)` vraća stanje `DECLARATIONS`. Prije prvog poteza pozvati `resolve_declarations(state)`, koji vraća novo stanje `PLAYING`. Ako postoji belot, umjesto običnog razrješavanja pozvati `declare_belot(state, player)`; pobjeda nastaje stvarnom objavom, a ne samim skrivenim posjedovanjem u modelu.

Ako su se tijekom usporedbe izgovorili vrijednost ili završna karta, prije razrješavanja pozvati `announce_meld_value(state, player)` i po potrebi `announce_sequence_high(state, player)`. Ti pozivi validiraju stvarno najjače zvanje i bilježe samo izgovoreni detalj. Istinite najave prisutnosti redom od igrača desno od djelitelja i sva pobjednička pokazivanja sadržana su u `meld_contest` nakon razrješavanja. Bela ne sudjeluje u usporedbi običnih zvanja i ne objavljuje se unaprijed.

Belu najaviti pozivom `play_card(state, player, card, announce_bela=True)` pri prvom odigravanju adutskog kralja ili dame. Običan potez koristi zadano `False`. Bodovi se priznaju tek u završnom obračunu ako je par osvojio barem jedan štih.

`settle_play(state)` vraća `DealResult` nakon osam štihova ili `BelotResult` nakon objave belota. Belot ima pobjednički par i pokazane karte, a nema običan upis bodova. Svaki poziv vraća novo stanje: potrebno ga je sačuvati za sljedeću operaciju.

## Sljedeći koraci

1. Isprobavanje dashboarda na stvarnim dijeljenjima i poboljšanje praktičnosti unosa.
2. Statističko uzorkovanje skrivenih raspodjela, uz već postojeća sigurna ograničenja iz legalnog igranja.
3. Simulacijske procjene i rangiranje poteza.
4. Zvanje aduta i modeliranje talona prije njegova otkrivanja.
5. API i korisničko sučelje prema stabilnom ugovoru enginea.

Detaljna referenca: [pravila](RULES.hr.md), [framework](FRAMEWORK.hr.md) i [workflow](WORKFLOW.hr.md).

# Unos stvarne partije bele

Ovaj način rada poznaje samo tvoju ruku i informacije koje uneseš iz stvarne igre. Prati legalnost, štihove, zvanja, belu, bodove i završetak partije. Statističko rangiranje poteza još nije dodano.

## Pokretanje

Glavni **START_BELA.cmd** otvara dashboard. Za tekstualni način iz terminala u projektnom folderu pokreni `.\START_BELA.cmd --text`. Pokretač koristi projektni Python ako postoji, zatim Python dostupan uz ovu Codex instalaciju, a inače naredbu `python`.

Otvori terminal u projektnom folderu i pokreni:

```powershell
python app/run.py --text
```

Nije potrebna instalacija paketa ni postavljanje `PYTHONPATH` za taj pokretač. Potreban je dostupan Python 3.11 ili noviji. Isti način rada dostupan je kao `python -m bela track` ako je paket instaliran ili `app/src` postavljen na `PYTHONPATH`.

Za nastavak spremljene korisničke partije:

```powershell
python app/run.py --text --load saves/moja_partija.player.json
```

Ako želiš unaprijed zadati naziv datoteke za spremanje:

```powershell
python app/run.py --text --save saves/moja_partija.player.json
```

Bez zadane putanje svaka nova partija dobiva vlastitu datoteku u folderu `partije`, tako da nova partija ne prepiše prethodnu. Svaki prihvaćen unos automatski se sprema. Pri izlasku sprema se ponovno. Ako spremanje ne uspije, program kaže da su podaci ostali u memoriji i omogućuje pokušaj naredbom `spremi`.

## Početni podaci

Program pita za naziv partije, tvoje mjesto, djelitelja, ukupan rezultat prije dijeljenja, zvatelja, adut i tvojih početnih osam karata nakon talona. Prazan odgovor prihvaća prikazanu zadanu vrijednost.

Igrači 0, 1, 2, 3 slijede redoslijed igranja. Parovi su 0+2 i 1+3. Rezultat se uvijek unosi kao par 0 : par 1, čak i kada pripadaš paru 1. Prvi igra djelitelj + 1, uz povratak s 3 na 0.

Oznake boja su H za herc, S za pik, D za karo i C za tref. Za adut se prihvaćaju i nazivi, examplesce `herc`, `zelena`, `bundeva` ili `žir`. Karte se zapisuju kao `H_J`, `S_10`, `D_A`, `C_7`. Rangovi su 7, 8, 9, 10, J, Q, K, A. Unosi karata odvajaju se razmacima.

## Zvanja i javne informacije

Zabilježi ono što je stvarno izgovoreno ili pokazano. Nepoznat podatak ostavi nepoznatim.

```text
ima 1 da
zvanje 1 50
vrh 1 K
pokazi 1 S_10 S_J S_Q S_K
zvanja 1
```

To znači: igrač 1 ima zvanje, rekao je 50, njegov niz završava kraljem, pokazao je navedene karte, a par 1 osvojio je pravo na zvanja. Unesi sve pokazane kombinacije obaju članova pobjedničkog para prije završne naredbe `zvanja 1`. Vlastita zvanja, ako pripadaš pobjedničkom paru, program prepoznaje iz tvoje početne ruke i bilježi njihovo obvezno pokazivanje.

Gubitničke karte ne treba pokazivati ako nisu pokazane u stvarnoj igri. Izgovorena vrijednost ili završna karta ipak ostaje u evidenciji. `pokazi` navodi vlasnika i sve stvarno pokazane karte; karta smije sudjelovati u više vrsta zvanja.

Ako običnih zvanja nema:

```text
zvanja nema
```

To je potvrda da nema običnih zvanja, a ne preskakanje nepoznatih zvanja. Ako u tvojoj ruci postoji zvanje ili ranije najave tome proturječe, unos se odbija. Bela ne spada u ovu usporedbu i najavljuje se tijekom odigravanja.

Interaktivna evidencija dopušta bilježenje poznatih javnih podataka bez obveznog unosa cijelog usmenog razgovora. Ne automatizira pitanja među igračima i ne pretpostavlja da gubitnik ima točno određene nepokazane karte.

## Odigravanje i bodovi

Unosi stvarni redoslijed:

```text
potez 0 S_9
potez 1 H_7
potez 2 S_7
potez 3 H_9
```

Možeš koristiti i `igraj H_7` za igrača koji je upravo na redu. Nakon četvrte karte program određuje pobjednika i vodi ga u sljedeći štih. Prikazuje tvoju preostalu ruku i legalne karte kada si na potezu.

`stanje`, `ruka` i `legalno` prikazuju pregled. Tijekom igre bodovi karata prikazuju se samo za završene štihove. Ukupan rezultat partije mijenja se tek pri završnom obračunu dijeljenja, nakon zadnjeg štiha, dodataka i eventualnog pada.

## Bela i belot

Za belu dodaj riječ `bela` uz prvi odigrani adutski kralj ili damu:

```text
potez 0 H_Q bela
```

Protivnička najava otkriva i posjedovanje druge karte bele u tom trenutku. Zakašnjela najava na drugoj karti nije dopuštena. Bez riječi `bela` potez se evidentira bez najave; naknadna ispravka dopuštena je ako si samo pogrešno prepisao stvarno izgovorenu najavu. Bodovi se priznaju tek ako par osvoji barem jedan štih.

Za vlastiti belot dovoljno je `belot 0`, uz svoje stvarno mjesto. Za tuđi belot navedi sve pokazane karte, examplesce:

```text
belot 1 C_7 C_8 C_9 C_10 C_J C_Q C_K C_A
```

Sve navedene karte moraju biti moguće za tog igrača; primjer nije dopušten ako ti već imaš neku od tih karata. Belot završava partiju bez redovnog upisa bodova.

## Ispravci

`povijest` prikazuje aktivne unose trenutačnog dijeljenja s brojevima. Za zamjenu, brisanje ili dodavanje propuštene informacije:

```text
ispravi 3 potez 1 H_8
obrisi 3
umetni 1 pokazi 1 S_7
nazad
```

`umetni 1` dodaje novi događaj prije dosadašnjeg prvog unosa. To omogućuje dodavanje zaboravljenog pokazivanja prije zaključenih zvanja i već odigranih karata. Pri ispravku i umetanju poteza navedi igrača izričito naredbom `potez`, kako bi se izbjegla zamjena s igračem koji je trenutačno na redu.

`nazad` uklanja posljednji aktivni unos. `postavke` otvara ponovni unos početne ruke, djelitelja, zvatelja, aduta i početnog rezultata. Tvoje mjesto u partiji ostaje isto.

Svi kasniji unosi provjeravaju se ponovno. Ako ispravak promijeni pobjednika štiha pa kasniji redoslijed više nije moguć, ispravak se odbija i postojeća partija ostaje netaknuta. Tada najprije ukloni pogrešan nastavak ili napravi drugi odgovarajući ispravak. Povijest naredbi čuva stari unos i samu izmjenu u datoteci. Ispravci se trenutačno odnose na aktualno dijeljenje; uređivanje starijih dijeljenja nakon početka novoga još nije dodano.

## Spremanje i novo dijeljenje

```text
spremi
spremi "saves/Moja večernja partija.player.json"
ucitaj "saves/Moja večernja partija.player.json"
dalje
izlaz
```

Naredba `spremi` s putanjom postavlja novu ciljnu datoteku za daljnje automatsko spremanje; postojeći cilj zamjenjuje se. `dalje` nakon završenog dijeljenja pita samo za novu ruku, zvatelja i adut. Rezultat i djelitelj prenose se automatski. Partija koja ima pobjednika ne može započeti sljedeće dijeljenje.

Korisnički zapis sadrži samo tvoju početnu ruku, javne podatke i povijest izmjena. Potpuni simulatorski zapisi iz ranije verzije koriste drugi format i otvaraju se razvojnim načinom `python -m bela --load ...`; ne učitavaju se kao korisničke partije.

## Što provjera može zaključiti

Program odbija duple karte, pogrešan redoslijed, tvoje nelegalne poteze, proturječno vlasništvo i zajednički nemoguće najave ili povijest. Za tuđe poteze provjerava postoji li barem jedna raspodjela skrivenih karata koja bi sve uneseno učinila legalnim. Ne dodjeljuje vjerojatnosti tim raspodjelama niti smatra pronađenu raspodjelu stvarnom.

Teža provjera ima granicu izračuna. Ako je dosegne, jasno kaže da unos nije prihvaćen zbog nedovršene provjere; ne proglašava ga dokazano pogrešnim. Možeš prvo dodati stvarno pokazane karte ili precizniju javnu najavu i pokušati ponovno. Za sada počinjemo od početnih osam karata i bilježimo sve poteze dijeljenja; početak usred igre s izgubljenom poviješću još nije podržan.

Za isprobavanje bez upisivanja početnih podataka:

```powershell
python app/run.py --text --load examples/player_match.json --save saves/isprobavanje.player.json
```

To je pokazni zapis; uz navedeni `--save` nastavak se sprema u tvoju probnu datoteku, pa se izvorni primjer čuva.

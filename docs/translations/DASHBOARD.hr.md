# Lokalni Bela dashboard

Dashboard je početno vizualno sučelje za testiranje postojećeg Python enginea. Otvara se u pregledniku, radi na tvojem računalu i sprema partije u projekt. Ne zahtijeva instalaciju dodatnih paketa ni vanjski račun.

## Pokretanje

Na Windowsu dvaput klikni **START_BELA.cmd**. Otvorit će se preglednik na adresi `http://127.0.0.1:8765`. Prozor pokretača ostavi otvoren dok koristiš dashboard. Zatvaranje poslužitelja: Ctrl+C u tom prozoru.

Možeš ga pokrenuti i iz projektnog foldera:

```powershell
python app/run.py
```

Ako je port zauzet:

```powershell
python app/run.py --port 8766
```

`--no-browser` pokreće poslužitelj bez automatskog otvaranja preglednika. Dostupno je i `python -m bela dashboard` kada je paket instaliran ili je `app/src` na `PYTHONPATH`.

## Prva proba

1. Klikni **Isprobaj primjer**. Otvara se zasebna kopija, a izvorni pokazni zapis ostaje netaknut.
2. Odaberi legalnog herc kralja iz svoje ruke ili iz birača desno, pa klikni **Zabilježi potez**. U primjeru je bela već najavljena na prethodnoj dami.
3. Otvori **Povijest unosa**. Možeš urediti, obrisati ili umetnuti događaj prije postojećeg unosa. Svaka promjena provjerava cijeli nastavak.
4. Otvori **Moje partije** i ponovno učitaj spremljeni zapis. Pri svakom prihvaćenom unosu datoteka se automatski ažurira.

## Nova stvarna partija

**Nova partija** otvara obrazac za ime, tvoje mjesto, djelitelja, zvatelja, adut, rezultat i početnih osam karata nakon talona. Karte biraš klikom; potrebno je točno osam različitih karata.

Mjesta 0–3 slijede redoslijed igranja. Par 0 čine 0 i 2, a par 1 čine 1 i 3. Rezultat u obrascu uvijek je po tom rasporedu. Na stolu se partner prikazuje nasuprot tebi, a ostala mjesta u smjeru dogovorene igre.

U kartici **Zvanja** unosiš samo javno poznate podatke: ima/nema, izgovorenu najjaču vrijednost, završnu kartu niza, pokazane karte ili belot. Nakon pokazivanja svih pobjedničkih zvanja potvrdi ishod običnih zvanja. Vlastita pobjednička zvanja engine može prepoznati iz tvoje ruke. Nepoznate protivničke karte ne unose se niti se izmišljaju.

U kartici **Unos poteza** odabireš kartu igrača koji je na redu. Na svojem potezu možeš kliknuti i kartu iz vlastite ruke. Zelena oznaka znači da je karta legalna, a ne da je strateški najbolja. Najavu bele označi samo ako je pravodobno izgovorena uz pripadajuću kartu. Engine provjerava stvarnu mogućnost i pravodobnost.

Štihovi, bodovi karata i trenutni rezultat prikazuju se automatski. Upis bodova partije mijenja se nakon završnog obračuna, uključujući pad, zvanja i dodatke. Gumb **Sljedeće dijeljenje** prenosi rezultat i pomiče djelitelja; pojavljuje se nakon završetka dijeljenja ako partija još nije završena.

## Spremanje i povijest

Dashboard čuva svoje korisničke partije u `saves/dashboard`, svaku pod vlastitim identitetom. **Preuzmi zapis** izvozi otvorenu partiju kao JSON. **Uvezi datoteku** na stranici Moje partije prihvaća postojeći korisnički zapis iz tekstualnog sučelja i stvara zasebnu kopiju. Potpuni simulatorski arhivi nisu isti format i ne mogu se uvesti kao korisničke partije.

**Uredi postavke** omogućuje promjenu početnih podataka aktualnog dijeljenja. Povijest omogućuje strukturirani ispravak događaja bez pisanja naredbi. Ako promjena učini nastavak nemogućim, obrazac ostaje otvoren s razlogom, a partija se ne mijenja. Izmjene se čuvaju u povijesti zapisa. Ranija dijeljenja nakon početka novoga trenutačno se mogu pregledati, ali ne uređivati.

Ova verzija ima jednu otvorenu partiju po poslužitelju. Više tabova preglednika dijeli to stanje; zastarjeli unos se odbija i prikaz osvježava. Nakon ponovnog pokretanja izaberi spremljenu partiju u Moje partije.

## Arhitektura za daljnji razvoj

```text
Preglednik
  index.html + style.css + app.js
        ↓ JSON zahtjevi
Lokalni HTTP sloj
  dashboard.py
        ↓ postojeće naredbe
Python engine
  tracking.py → pravila i provjera mogućih skrivenih raspodjela
  user_storage.py → korisnički zapisi i povijest izmjena
```

Početni prikaz koristi HTML, CSS i JavaScript bez procesa gradnje i bez udaljenih biblioteka. Time je prototip odmah pokretljiv. Pravila i stanje nisu kopirani u preglednik: svi unosi potvrđuju se u Pythonu. Predloženi kasniji TypeScript i React mogu preuzeti prikaz kroz isti API; lokalni HTTP sloj tada se po potrebi može zamijeniti FastAPI-jem.

Glavni API ugovori:

| Putanja | Svrha |
| --- | --- |
| `GET /api/state` | Dopušteni pogled otvorene partije i spremljeni zapisi |
| `POST /api/new` | Nova partija s vlastitom rukom |
| `POST /api/demo` | Zasebna kopija pokazne partije |
| `POST /api/command` | Dodavanje, ispravak, umetanje, brisanje, postavke ili novo dijeljenje |
| `POST /api/load` | Učitavanje zapisa iz dashboardove zbirke |
| `POST /api/import` | Validacija i uvoz korisničkog JSON-a kao nove kopije |
| `GET /api/export` | Izvoz otvorenog korisničkog zapisa |
| `GET /api/rules` | Tekst dogovorenih pravila |

Svaki POST uključuje očekivani identitet partije i broj izmjene. Poslužitelj serijalizira izmjene i mijenja memorijsko stanje tek nakon uspješnog spremanja. API se veže na `127.0.0.1`; ovaj poslužitelj je lokalni razvojni alat, ne javni hosting ili višekorisnički servis.

## Što dodajemo sljedeće

1. Povratne informacije nakon nekoliko stvarno unesenih dijeljenja i poboljšanja brzine unosa.
2. Statističko uzorkovanje mogućih skrivenih raspodjela.
3. Usporedba legalnih poteza i procjene ishoda, uz jasno prikazanu nesigurnost.
4. Kasnije zvanje aduta na šest karata i vizualna poboljšanja buduće aplikacije.

Prostor za statistiku u dashboardu izričito je označen kao buduća funkcionalnost. Ne prikazuje izmišljene vjerojatnosti. Zahtjevnija provjera unosa i dalje može dosegnuti postojeću granicu izračuna; tada je razlog vidljiv, a prethodno stanje ostaje sačuvano.

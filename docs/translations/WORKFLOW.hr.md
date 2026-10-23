# Plan gradnje Bela enginea

Datum: 23. listopada 2026. Ovaj plan provodi arhitekturu iz [FRAMEWORK.md](FRAMEWORK.hr.md) i pravila iz [RULES.md](RULES.hr.md).

Početni engine implementiran je u Pythonu. Postoje model karata, legalni potezi, simulator od osam štihova, obračun, detekcija i usporedba zvanja, pokazivanje pobjedničkih zvanja, pravodobna bela i belot. Faza zvanja u simulatoru sažeto razrješava istinite najave; korisnički tijek pitanja i odgovora, sesije s djelomično poznatim rukama i ispravci opisani su u nastavku. Zvanje aduta i skriveni talon ostaju kasnija faza. Pokretanje i trenutačne granice opisani su u [razvojnim uputama](DEVELOPMENT.hr.md).

Spremanje je prvotno dodano za simulator: `MatchSession` čuva niz dijeljenja, a verzionirani JSON omogućuje nastavak i usred štiha. Učitavanje rekonstruira stanje legalnim odigravanjem svih spremljenih akcija i provjerava prijenos rezultata i djelitelja. Ti zapisi čuvaju sve simulatorske ruke; novi korisnički format opisan je u nastavku.

Tekstualni unos stvarne igre sada je dodan kroz `app/run.py --text` i `UserMatch`: samo vlastita ruka, javne najave, pokazivanja i potezi, legalne vlastite karte, bodovi, ispravci, povijest izmjena i automatsko spremanje. Tuđa legalnost provjerava se postojanjem barem jedne zajednički moguće skrivene raspodjele uz vremenska ograničenja iz poteza. To je provjera mogućnosti, ne statističko uzorkovanje. Teški slučajevi imaju izričit računalni budžet. Interaktivni razgovor pri zvanju još nije automatiziran. Primjena je opisana u [uputama](USER_GUIDE.hr.md).

Početni vizualni dashboard dodan je ranije u razvoju za praktično testiranje: stol, izbor karata, unos javnih informacija, povijest s ispravcima, zbirka partija i uvoz/izvoz. Koristi isti engine preko lokalnog HTTP API-ja. To ne znači da su faze statističkog savjetovanja dovršene; sljedeće nadograđujemo engine i prikaz usporedbom stvarnih situacija. Pokretanje i ugovori opisani su u [DASHBOARD.md](DASHBOARD.hr.md).

Radimo u malim cjelinama koje se mogu odigrati, pregledati i provjeriti. Svaka faza završava konkretnim demonstracijskim primjerom i provjerom prihvaćanja. Prelazak u sljedeću fazu ovisi o kvaliteti rezultata, a ne o količini napisanog koda. Procjenu trajanja dajemo nakon prvog mjerljivog dijela implementacije.

## 1. Pravila i model igre

**Gradimo:** oznake 32 karte, mjesta i parove, rangove i vrijednosti, legalne poteze, pobjednika štiha, zvanja i obračun dijeljenja i partije. Odvajamo izračun bodova od dopuštenog znanja igrača.

**Demonstracija:** četiri unesene ruke mogu odigrati svih osam štihova, a sustav odbija nelegalne poteze i daje ispravan konačni upis. Prikaz svih ruku postoji samo u razvojnom simulatoru.

**Provjere prihvaćanja:**

- Primjeri iz pravila imaju očekivane rezultate: 81 : 81 znači pad, 82 : 80 prolaz, štiglja 252, bela bez štiha 0.
- Posebno pokriti iber uz partnera koji nosi, praćenje nakon presijecanja, slabiji adut kad nema jačeg i zabranu adutiranja uz posjedovanje početne boje.
- Provjeriti zvanja koja se preklapaju, usporedbu nizova po završnoj karti, belot i izjednačenje iznad 1000.
- Svaka karta igra se najviše jednom, broj karata pada ispravno i zbroj bodova karata ostaje 152. Sve legalne potpune raspodjele imaju završetak.

**Rezultat faze:** pouzdana biblioteka pravila i skup razumljivih scenarija. Ovo je prvi konkretan implementacijski korak.

## 2. Sesija i povijest događaja

**Gradimo:** unos vlastite ruke, djelitelja, aduta, zvatelja, ukupnog rezultata, javnih zvanja i pojedinačnih poteza. Dodajemo serijalizaciju u JSON, ponovno učitavanje, ispravak događaja i revizije.

**Demonstracija:** jednu stvarnu ili ručno složenu partiju možemo unositi potez po potez, spremiti, otvoriti i nastaviti. Pogrešno unesena karta može se ispraviti uz ponovni obračun.

**Provjere prihvaćanja:** ponovno odigravanje iste povijesti daje isto stanje; spremanje i učitavanje čuva sadržaj; ispravak ne ostavlja stare zaključke; duplikati i pogrešan redoslijed daju razumljivu grešku.

**Rezultat faze:** aplikacijska osnova bez statističkih savjeta. Korisnički pogled već skriva tuđe neotkrivene karte.

## 3. Znanje i moguće skrivene karte

**Gradimo:** obvezna ograničenja iz pravila, vremensko praćenje pokazivanja i igranja karata, zapis razloga zaključka i generator mogućih raspodjela. Najave zvanja obrađuju se kao ograničenja kombinacija, a ne kao automatsko otkrivanje karata.

**Demonstracija:** nakon odbacivanja umjesto praćenja app može pokazati „igrač nema pik” i događaj iz kojeg to slijedi. Svaka uzorkovana raspodjela odgovara cijeloj poznatoj povijesti.

**Provjere prihvaćanja:**

- Na malim slučajevima potpuno nabrojiti moguće raspodjele i usporediti ih s generatorom.
- Provjeriti raspodjelu uzoraka i kapacitete svih ruku, ne samo dopuštenost pojedinačnih karata.
- Odbaciti zajednički nemoguća zvanja ili vlasništva čak i kada svaka pojedinačna tvrdnja izgleda moguća.
- Testovima razlikovati izostanak boje od izostanka jače karte te izostanak zaključka nakon presijecanja.
- Kod proturječja prepoznati konkretan sukob, a kod sporog uzorkovanja javiti računalno ograničenje.

**Rezultat faze:** statistika mogućih vlasnika karata pod izričito navedenim početnim modelom.

## 4. Prvi savjeti kroz simulacije

**Gradimo:** slučajnu legalnu politiku, jednostavnu heurističku politiku, simulator nastavka dijeljenja i usporedbu svih naših legalnih poteza. Svaki simulirani igrač prima samo svoj pogled.

**Demonstracija:** za odabranu poziciju dobivamo rangirane karte, očekivani upis nakon pada i procjenu našeg prolaza ili rušenja. Dodavanje tuđeg poteza ažurira preporuke.

**Provjere prihvaćanja:**

- Isti seed, verzija i stanje daju ponovljiv rezultat u definiranom načinu rada.
- Promjena nedostupnih skrivenih podataka uz isti pogled ne mijenja ponašanje politike ili savjetnika.
- Na potpuno poznatim malim završnicama provjeriti rezultate točnim pretraživanjem.
- Povećanje broja uzoraka provjerava stabilnost procjena, uz mjerenje preostale nesigurnosti.
- Jedan prisilni legalni potez vraća se odmah, bez nepotrebnog rangiranja.
- Rezultati jasno navode da su procjene uvjetovane početnim politikama i modelom raspodjele.

**Rezultat faze:** prvi upotrebljiv engine za analizu dijeljenja. Ovo je prva verzija za zajedničko isprobavanje na stvarnim situacijama.

## 5. Kvaliteta odluka i jače pretraživanje

**Gradimo:** bolju raspodjelu računalnog vremena, prilagođeni ISMCTS ili drugu opravdanu metodu, nekoliko modela legalne igre te zasebnu evaluaciju vodećih poteza. Eksperimentalne promjene uspoređujemo sa zamrznutom prethodnom verzijom.

**Demonstracija:** skup pozicija na kojima sustav prepoznaje bliske izbore i na nekim pozicijama pronalazi bolji nastavak od početnih simulacija.

**Provjere prihvaćanja:** usporedbe na unaprijed odvojenim dijeljenjima, zamjena mjesta i parova na istim raspodjelama, intervali uparenih razlika rezultata te odsutnost curenja informacija. Više vremena ili složeniji algoritam sami po sebi nisu kriterij poboljšanja.

**Rezultat faze:** prva mjerljivo poboljšana verzija savjetnika, s dokumentiranim granicama kvalitete.

## 6. Ukupni rezultat i strategija partije

**Gradimo:** simulaciju budućih dijeljenja, vrijednost ukupnog rezultata i sljedećeg djelitelja te rangiranje prema pobjedi u partiji. Predviđanje je uvjetovano definiranim politikama zvanja i igranja kroz buduće partije.

**Demonstracija:** istu ruku analiziramo pri više ukupnih rezultata. Na odabranim scenarijima provjerimo kada je opravdano promijeniti preferenciju rizika i kada preporuka treba ostati ista.

**Provjere prihvaćanja:**

- Svi završni rezultati daju ispravan ishod, uključujući pad, istodobni prelazak granice, belot i izjednačenje.
- Procijenjene vjerojatnosti provjeravaju se na neovisnim simuliranim partijama prema istom modelu; pratimo kalibraciju, npr. skup situacija procijenjenih oko 70 % treba pobjeđivati približno toliko često.
- Kalibracija u simulatoru odvojena je od kvalitete protiv ljudi. Stvarne zapise koristimo za daljnju provjeru kad ih prikupimo.
- Privremeni cilj bodovne razlike ostaje dostupan za dijagnostiku; glavna preporuka jasno navodi koristi li cilj pobjede u partiji.

**Rezultat faze:** savjetnik koji koristi ukupan rezultat za procjenu dugoročnog ishoda.

## 7. Prva app

**Gradimo:** jednostavan stol s četiri mjesta, izbor vlastitih karata, unos zvanja i tuđih poteza, prikaz štihova, ukupnog rezultata i rangiranih savjeta. Dodajemo spremanje, povijest i ispravke. API slijedi ugovore iz frameworka.

**Demonstracija:** cijelo dijeljenje unosimo bez razvojnih alata. Aplikacija nakon svakog unosa pokaže novo stanje i analizu odgovarajuće revizije.

**Provjere prihvaćanja:** cijelo dijeljenje od unosa do upisa; ispravljanje rane pogreške; prekid i nastavak; odbacivanje zastarjelog rezultata analize; razumljivi izrazi; čitljivost na telefonu. Rano možemo napraviti skicu sučelja, ali funkcionalnu aplikaciju spajamo nakon stabilizacije ugovora enginea.

**Rezultat faze:** lokalna app za korištenje i prikupljanje povratnih informacija. Cilj odziva za početno isprobavanje može biti brza procjena unutar nekoliko sekundi, uz opciju dulje analize; konkretan budžet potvrđujemo mjerenjem na korisnikovu računalu.

## 8. Savjetovanje pri zvanju aduta

**Gradimo:** usporedbu četiri boje i dalje na prvih šest karata, nepoznati vlastiti talon, model kasnijih odluka pri zvanju i mus.

**Demonstracija:** prije gledanja talona app rangira dostupne odluke i zatim prelazi u odigravanje nakon stvarnog odabira aduta.

**Provjere prihvaćanja:** ne koriste se vlastite buduće dvije karte; dalje nije dopušten na musu; partnerove ruke ostaju skrivene; simulacija dalje uključuje preostale igrače; već završeno zvanje nema naknadnih odluka.

**Rezultat faze:** podržan savjetodavni tijek od zvanja do kraja partije.

## 9. Napredni unos i učenje

Nakon stabilne aplikacije biramo proširenja prema stvarnoj koristi:

- Početak usred dijeljenja uz nepotpunu povijest i jasno označena ograničenja.
- Slobodan tekst i glas prevedeni u postojeće događaje.
- Fotografije ruke ili stola s potvrdom prepoznatih karata.
- Analiza završene partije i usporedba odigranog s preporučenim potezom.
- Modeli stilova partnera i protivnika, uz mjerenje koliko podataka treba za pouzdanu prilagodbu.
- Učenje iz samostalnog igranja i ubrzavanje izmjerenih uskih grla.
- Distribucija na telefonu, sinkronizacija ili poslužiteljsko računanje ako se pokažu potrebnima.

Svako proširenje zadržava isti model pravila i događaja. Vanjski AI servis može pomoći pri razumijevanju unosa, ali pravila, bodovanje i statističke preporuke ostaju provjerljivi dijelovi sustava.

## Radni ciklus za svaku promjenu

1. Zapisati primjer problema i očekivani rezultat.
2. Utvrditi na koji sloj promjena utječe i koji je dopušteni pogled igrača.
3. Implementirati najmanju cjelovitu promjenu.
4. Provjeriti relevantne rubne slučajeve i postojeće scenarije tog sloja.
5. Ako se mijenja strategija ili statistika, provesti usporedbu na odvojenom skupu scenarija s istim uvjetima za obje verzije.
6. Spremiti primjer i metapodatke za ponavljanje analize: verzije pravila i modela, stanje, seed i računalni budžet.
7. Pregledati rezultat kao korisnik i ažurirati dokumentaciju ako se ugovor ili ponašanje promijenilo.

Za svaki problem iz stvarne igre spremamo minimalan anoniman zapis dovoljan da ga ponovimo. Skup primjera za razvoj odvajamo od skupa na kojem mjerimo kvalitetu. Postavke ne prilagođavamo potajno završnom evaluacijskom skupu.

## Što prvo radimo

Spremanje i tekstualni korisnički unos iz faze 2 postoje, uključujući ispravke aktualnog dijeljenja. Sljedeće isprobavamo stvarne situacije i gradimo statističko uzorkovanje nad postojećim sigurnim ograničenjima. Korisnički unos i preporuke povezat ćemo preko istih opažanja, bez davanja skrivenih ruku savjetniku.

Ovaj dokument planira rad; status početnog kostura naveden je na vrhu. Opis faze sam po sebi ne znači da je faza implementirana.

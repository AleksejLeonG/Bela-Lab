# Pravila hrvatske bele za četiri igrača

Referentna specifikacija za izradu enginea. Verzija 1.0, 23. listopada 2026.

Dokument definira dogovorenu varijantu igre, legalne poteze, obračun bodova i informacije dostupne igraču. Uključuje potvrde iz razgovora i služi kao osnova za implementaciju i provjeru enginea. Posebna pravila ove varijante imaju prednost pred pravilima drugih inačica bele.

## 1. Igrači, parovi i cilj

Igraju četiri igrača podijeljena u dva stalna para. Partneri sjede jedan nasuprot drugome.

Za potrebe enginea igrači se mogu označiti brojevima 0, 1, 2 i 3, redoslijedom igranja:

- Par A: igrači 0 i 2.
- Par B: igrači 1 i 3.

Igra se u smjeru suprotnom od kazaljke na satu.

Partneri zajednički skupljaju bodove. Bodovi pojedinih igrača istog para zbrajaju se.

Pojmovi:

- Štih: četiri odigrane karte, po jedna od svakog igrača.
- Dijeljenje: jedan krug od podjele karata do konačnog obračuna osam štihova.
- Partija: niz dijeljenja do pobjede jednog para.
- Zvanje aduta: određivanje adutske boje.
- Zvanja: kombinacije karata koje donose dodatne bodove.

## 2. Špil

Koristi se špil od 32 karte.

Postoje četiri boje:

- Herc / srce / crvena.
- Pik / list / zelena.
- Karo / bundeva.
- Tref / žir.

Svaka boja sadrži osam karata:

7, 8, 9, 10, dečko, dama, kralj i as.

Za zapis u engineu mogu se koristiti oznake:

- J = dečko.
- Q = dama.
- K = kralj.
- A = as.

Svaka karta pojavljuje se točno jednom.

## 3. Dijeljenje

Djelitelj promiješa karte i ponudi igraču sa svoje lijeve strane da presiječe špil.

Karte dijeli u smjeru suprotnom od kazaljke na satu, počevši od igrača sa svoje desne strane.

Svaki igrač dobiva:

1. Tri karte.
2. Još tri karte.
3. Još dvije karte koje se odvojeno ostavljaju kao njegov talon.

Svaki igrač na kraju ima osam karata, ali tijekom određivanja aduta smije znati samo prvih šest.

Dvije karte talona ne smiju se pogledati prije nego što je adut određen.

Igrač prvih šest karata podiže kada dođe na red za određivanje aduta.

Nakon svakog dijeljenja uloga djelitelja prelazi na sljedećeg igrača u smjeru igranja.

## 4. Određivanje aduta

Prvi odlučuje igrač s desne strane djelitelja.

Kada dođe na red, igrač može:

- Odabrati jednu od četiri boje kao adut.
- Reći „dalje” i prepustiti odluku sljedećem igraču.

Čim netko odredi adut, određivanje aduta završava.

Ako prva tri igrača kažu „dalje”, djelitelj mora odrediti adut. To se naziva „mus”.

U ovoj osnovnoj varijanti:

- Postoji jedan krug određivanja aduta.
- Nema licitiranja brojčane vrijednosti ugovora.
- Djelitelj na musu ne može ponovno reći „dalje”.
- Mus ne smanjuje broj bodova potreban za prolaz.

Nakon određivanja aduta svi igrači podižu svoje dvije karte talona i pridružuju ih preostalima.

Par kojem pripada igrač koji je odredio adut naziva se par koji je zvao.

Drugi par pokušava srušiti par koji je zvao.

## 5. Jačina i bodovna vrijednost karata

### 5.1. Karte u adutu

Redoslijed od najjače prema najslabijoj karti:

J > 9 > A > 10 > K > Q > 8 > 7

Bodovne vrijednosti:

| Karta | Bodovi |
|---|---:|
| J | 20 |
| 9 | 14 |
| A | 11 |
| 10 | 10 |
| K | 4 |
| Q | 3 |
| 8 | 0 |
| 7 | 0 |

### 5.2. Karte izvan aduta

Redoslijed od najjače prema najslabijoj karti:

A > 10 > K > Q > J > 9 > 8 > 7

Bodovne vrijednosti:

| Karta | Bodovi |
|---|---:|
| A | 11 |
| 10 | 10 |
| K | 4 |
| Q | 3 |
| J | 2 |
| 9 | 0 |
| 8 | 0 |
| 7 | 0 |

### 5.3. Međusobno uspoređivanje boja

Svaki adut jači je od svake karte koja nije adut.

Ako u štihu nema aduta, štih može osvojiti samo karta početne boje.

Karta neke druge neadutske boje ne može osvojiti štih, bez obzira na svoju bodovnu vrijednost.

## 6. Zvanja

Zvanja se utvrđuju nakon podizanja talona, prije odigravanja prvog štiha, osim bele koja se najavljuje tijekom igre.

Zvanja se računaju iz osam karata pojedinog igrača. Karte partnera ne mogu se spojiti kako bi zajedno činile jedno zvanje.

### 6.1. Četiri jednake karte

- Četiri dečka: 200 bodova.
- Četiri devetke: 150 bodova.
- Četiri asa: 100 bodova.
- Četiri desetke: 100 bodova.
- Četiri kralja: 100 bodova.
- Četiri dame: 100 bodova.
- Četiri osmice: nema bodova.
- Četiri sedmice: nema bodova.

Ne primjenjuje se varijanta u kojoj četiri sedmice poništavaju protivnička zvanja.

### 6.2. Nizovi iste boje

Za nizove se koristi poseban redoslijed:

7, 8, 9, 10, J, Q, K, A.

Ovaj redoslijed vrijedi neovisno o tome je li boja adut.

Vrijednosti:

- Tri uzastopne karte iste boje: 20 bodova.
- Četiri uzastopne karte iste boje: 50 bodova.
- Pet uzastopnih karata iste boje: 100 bodova.
- Šest uzastopnih karata iste boje: 100 bodova.
- Sedam uzastopnih karata iste boje: 100 bodova.

Primjeri:

- 7–8–9: 20.
- 9–10–J–Q: 50.
- 10–J–Q–K–A: 100.

Jedan neprekinuti niz računa se jednom, kao cjelina. Primjerice, niz od pet karata ne donosi istodobno i dodatne bodove za trojke i četvorke sadržane u tom nizu.

### 6.3. Koji par ima pravo na zvanja

Uspoređuje se najjače pojedinačno zvanje svakog para.

Par s najjačim pojedinačnim zvanjem dobiva pravo na bodovanje svojih zvanja.

Tada se zbrajaju priznata zvanja obaju partnera tog para.

Drugi par ne dobiva bodove za svoja obična zvanja, čak ni ako bi njihov zajednički zbroj bio veći.

Bela je iznimka i ne ovisi o tome koji je par osvojio pravo na ostala zvanja.

### 6.4. Uspoređivanje zvanja

Primjenjuju se sljedeća pravila:

- Četiri dečka jača su od četiri devetke.
- Četiri devetke jače su od zvanja vrijednih 100 bodova.
- Četiri jednake karte koje vrijede 100 bodova jače su od niza vrijednog 100 bodova.
- Među četirima jednakim kartama vrijednim 100 bodova vrijedi: četiri asa > četiri desetke > četiri kralja > četiri dame.
- Kod nizova najprije se uspoređuje bodovna vrijednost: 100 > 50 > 20.
- Kod nizova iste bodovne vrijednosti jači je niz s višom završnom kartom. Za nizove od pet, šest i sedam karata duljina nema prednost pred završnom kartom.
- Primjer: pet karata 10–J–Q–K–A pobjeđuje šest karata 8–9–10–J–Q–K jer je as viši od kralja.
- Ako nizovi iste bodovne vrijednosti imaju istu završnu kartu, primjenjuje se prednost ranijeg igrača opisana u sljedećoj stavci.
- Kod potpuno jednakih zvanja prednost ima igrač koji je ranije imao pravo odrediti adut, računajući od igrača desno od djelitelja.

Ne primjenjuje se dodatna prednost samo zato što je niz u adutu.

Usporedbe uključuju naknadne potvrde korisnika za ovu varijantu igre.

### 6.5. Preklapanje zvanja

Dopušteno je da ista karta sudjeluje u različitim vrstama zvanja.

Primjerice, dama može istodobno biti dio četiriju dama i niza iste boje.

To ne znači da se svi podnizovi jednog neprekinutog niza zasebno boduju.

### 6.6. Najava i pokazivanje

Najava počinje od igrača desno od djelitelja i nastavlja se redom u smjeru igre. Svaki igrač govori ima li zvanja.

Ako zvanja postoje u suparničkim parovima, usporedba počinje od prvog igrača po redu koji je najavio zvanje. Njega se pita koliko ima, a on navodi vrijednost svojega najjačeg pojedinačnog zvanja. Protivnici navode višu vrijednost ako je imaju, examplesce 50.

Ako više suparničkih igrača ima niz iste vrijednosti, prvoga po redu pita se do koje karte ide niz. On govori najvišu kartu. Protivnik koji ima jače zvanje pokazuje svoje; inače traži od prvoga da pokaže svoje. Za usporedbu se primjenjuju sva pravila iz odjeljka 6.4, uključujući posebni poredak četiriju jednakih karata.

Par koji osvoji pravo na zvanja mora pokazati sva svoja zvanja koja se boduju. Gubitnički par ne mora pokazati nijedno svoje zvanje.

Izgovorene informacije ostaju javne i ako par izgubi pravo na zvanja. Engine mora odvojeno bilježiti najave, izgovorene vrijednosti i završne karte te stvarno pokazane karte i njihove vlasnike. Gubitak prava na zvanja ne briše ranije javno izgovorene informacije. Sama najava bodovne vrijednosti ne otkriva automatski sve karte igrača.

## 7. Bela

Bela je kralj i dama adutske boje u ruci istog igrača.

Vrijedi 20 bodova.

Bela se mora najaviti riječju „bela” kada igrač prvi put odigra jednu od tih dviju karata.

Može prvo odigrati kralja ili damu.

Pri odigravanju druge karte može reći „od bele”, ali to nije obvezno.

Ako bela nije pravodobno najavljena, ne boduje se.

Bela se može priznati i paru koji nije osvojio pravo na ostala zvanja.

Kralj i dama mogu biti dio drugih priznatih kombinacija, a bela se dodatno boduje.

Za priznanje bele par mora osvojiti barem jedan štih.

## 8. Belot

Belot znači da jedan igrač ima svih osam karata iste boje.

Belot donosi trenutačnu pobjedu u partiji, neovisno o dotadašnjem rezultatu. Ovo pravilo potvrđeno je za našu varijantu.

Ovo je posebna iznimka od uobičajenog završavanja dijeljenja i obračuna bodova.

Belot se ne obračunava kao običan niz od 100 bodova; njegova posljedica je završetak partije.

## 9. Početak i tijek igranja

Prvi štih započinje igrač s desne strane djelitelja, bez obzira na to tko je odredio adut.

Prvi igrač može odigrati bilo koju kartu iz svoje ruke.

Ostali igrači redom odigravaju po jednu kartu u smjeru suprotnom od kazaljke na satu, poštujući pravila legalnog odigravanja.

Nakon četvrte karte utvrđuje se pobjednik štiha.

Pobjednik uzima sve četiri karte za svoj par i započinje sljedeći štih.

Odigrava se osam štihova.

## 10. Pravila legalnog odigravanja

### 10.1. Obvezno praćenje početne boje

Početna boja je boja prve karte odigrane u štihu.

Ako igrač ima barem jednu kartu početne boje, mora odigrati kartu te boje.

Ne smije odigrati adut ili drugu boju dok može pratiti početnu boju.

### 10.2. Iber dok štih nije presječen adutom

Ako igrač prati početnu neadutsku boju i štih još nije presječen adutom, mora odigrati kartu jaču od trenutačno najjače karte početne boje, ako takvu kartu ima.

Ako ne može nadjačati, smije odigrati bilo koju svoju kartu početne boje.

Ne mora odigrati najjaču kartu koju ima. Mora samo odabrati neku od karata koje zadovoljavaju obvezu nadjačavanja.

Primjer:

- Prva karta je pik 8.
- Igrač ima pik 7, pik K i pik A.
- Mora odigrati pik K ili pik A.
- Ne smije odigrati pik 7.

### 10.3. Praćenje boje nakon presijecanja adutom

Ako je početna boja neadutska, a netko je već odigrao adut, igrač koji ima početnu boju i dalje je mora pratiti.

Međutim, više ne mora nadjačavati prethodne karte početne boje jer štih već osvaja adut.

Primjer:

- Adut je herc.
- Prvi igrač odigra pik 8.
- Drugi igrač odigra herc 7.
- Treći igrač ima pik 7 i pik A.
- Treći smije odigrati bilo koju od tih dviju pikovih karata.

### 10.4. Obvezno igranje aduta

Ako igrač nema početnu boju, ali ima adut, mora odigrati adut.

Obveza vrijedi i kada trenutačno štih osvaja njegov partner.

U ovoj varijanti nema oslobađanja od obveznog adutiranja zato što je partner najjači.

### 10.5. Nadjačavanje aduta

Ako igrač mora odigrati adut, a u štihu već postoji adut, mora odigrati jači adut od trenutačno najjačeg ako takav ima.

Ako nema jači adut, ali ima slabiji, odigrava neki od svojih slabijih aduta.

Ako je početna boja adut, igrač mora pratiti adut i nadjačati trenutačno najjači adut ako može.

Nadjačavanje aduta obvezno je kad god igrač prema ovim pravilima mora odigrati adut i može odigrati jači. Obveza vrijedi i kada partner trenutačno osvaja štih. Pravila praćenja početne boje iz odjeljaka 10.1 i 10.3 i dalje vrijede.

### 10.6. Slobodno odbacivanje

Ako igrač nema ni početnu boju ni adut, smije odigrati bilo koju kartu iz ruke.

Takva karta ne može osvojiti štih.

### 10.7. Partner ne ukida obveze

Pravila praćenja boje, ibera i adutiranja vrijede bez obzira na to osvaja li štih partner ili protivnik.

## 11. Određivanje pobjednika štiha

Ako je odigran barem jedan adut, štih osvaja najjači odigrani adut.

Ako nije odigran nijedan adut, štih osvaja najjača karta početne boje.

Sve bodovne vrijednosti četiriju karata pripadaju paru pobjednika štiha.

## 12. Bodovi iz štihova

Zbroj bodovnih vrijednosti svih karata u špilu iznosi 152.

Par koji osvoji posljednji, osmi štih dobiva dodatnih 10 bodova.

Zato obična igra bez zvanja ukupno vrijedi:

152 + 10 = 162 boda.

## 13. Štiglja — svi štihovi

Ako jedan par osvoji svih osam štihova, dobiva dodatnih 90 bodova.

Ukupna vrijednost igre bez zvanja tada iznosi:

152 + 10 + 90 = 252 boda.

Priznata zvanja pobjedničkog para dodaju se na taj iznos.

Par bez ijednog štiha nema pravo na bodove za zvanja, uključujući belu.

## 14. Uvjet za priznanje zvanja

Par mora osvojiti barem jedan štih kako bi mu se priznali bodovi zvanja.

Dovoljan je jedan štih koji osvoji bilo koji partner.

Štih ne mora sadržavati karte koje same nose bodove.

Pravilo vrijedi i za belu.

## 15. Prolaz i pad

Par koji je odredio adut mora osvojiti strogo više od polovice ukupnih bodova dijeljenja.

Pri obračunu se uzimaju bodovi štihova, posljednjeg štiha i priznatih zvanja, uključujući pravodobno najavljenu belu.

Ako je ukupan broj raspoloživih bodova T, najmanji broj bodova za prolaz iznosi:

floor(T / 2) + 1.

Primjeri:

| Ukupna vrijednost dijeljenja | Potrebno za prolaz |
|---|---:|
| 162 | 82 |
| 182 | 92 |
| 202 | 102 |
| 212 | 107 |
| 262 | 132 |

Ako oba para imaju jednak broj bodova, par koji je zvao pada.

I na musu vrijedi isti uvjet prolaza.

### 15.1. Kada par koji je zvao prođe

Svakom paru upisuje se broj bodova koji mu pripada nakon obračuna.

Primjer bez zvanja:

- Par koji je zvao osvoji 100 bodova.
- Protivnici osvoje 62 boda.
- Upisuje se 100 : 62.

### 15.2. Kada par koji je zvao padne

Paru koji je zvao ne upisuju se bodovi tog dijeljenja.

Protivnicima se upisuje cijela vrijednost dijeljenja.

Primjer bez zvanja:

- Par koji je zvao osvoji 80 bodova.
- Protivnici osvoje 82 boda.
- Konačni upis je 0 : 162.

Primjer sa zvanjima:

- Dijeljenje ukupno vrijedi 212 bodova.
- Par koji je zvao osvoji 106.
- Protivnici osvoje 106.
- Par koji je zvao pada.
- Konačni upis je 0 : 212.

Na papiru se pad može označiti crticom. Za računanje u engineu predstavlja nula upisanih bodova za taj par.

## 16. Ukupni rezultat i završetak partije

Oba para počinju s nula bodova.

Nakon svakog dijeljenja konačno obračunati bodovi dodaju se dotadašnjem ukupnom rezultatu.

Svako redovno dijeljenje odigrava se do kraja, uključujući svih osam štihova.

Nema ranijeg izlaska „vani” tijekom dijeljenja.

Tek nakon završetka dijeljenja i obračuna prolaza ili pada provjerava se pobjeda:

1. Ako nijedan par nema više od 1000 bodova, igra se novo dijeljenje.
2. Ako samo jedan par ima više od 1000 bodova, taj par pobjeđuje.
3. Ako oba para imaju više od 1000 bodova, pobjeđuje par s većim ukupnim rezultatom.

Točno 1000 bodova nije dovoljno za pobjedu.

Primjer:

- Prije dijeljenja rezultat je 980 : 970.
- Konačni upis dijeljenja je 90 : 72.
- Novi rezultat je 1070 : 1042.
- Pobjeđuje prvi par.

Pad se obračunava prije provjere pobjede. Bodovi koje je par prikupio tijekom igre, ali izgubio padom, ne mogu se koristiti za prelazak granice.

Ako oba para nakon dijeljenja imaju jednak rezultat iznad 1000, igra se dodatno dijeljenje. Isto se pravilo primjenjuje nakon svakog sljedećeg izjednačenja dok se ne dobije pobjednik.

Posebno pravilo belota iz odjeljka 8 zasebna je iznimka i odmah završava partiju.

## 17. Nepravilno odigravanje

Nepravilnosti uključuju:

- Nepraćenje početne boje kada ju igrač ima.
- Neizvršavanje obveznog ibera.
- Neigranje aduta kada je obvezan.
- Igranje karte koju igrač nema.
- Igranje izvan reda.
- Nedopušteno gledanje skrivenih karata.

Prema izvoru, za kršenje pravila odigravanja protivničkom paru upisuje se 162 boda i sva najavljena zvanja tog dijeljenja, a dijeljenje se prekida.

Izvor posebno navodi kaznu od 162 boda za prerano podizanje karata.

U normalnoj simulaciji engine treba spriječiti nelegalne poteze. Kazneni obračun potreban je samo ako želimo podržati bilježenje nepravilnosti iz stvarne igre.

## 18. Informacije dostupne igraču i engineu

Tijekom određivanja aduta igrač zna:

- Svojih prvih šest karata kada ih smije pogledati.
- Tko je djelitelj.
- Tko je prije njega rekao „dalje”.
- Dotadašnji ukupni rezultat.

Ne zna svoje dvije karte talona prije određivanja aduta.

Nakon određivanja aduta igrač zna:

- Svih svojih osam karata.
- Adut i identitet igrača koji ga je odredio.
- Javno najavljena i pokazana zvanja.
- Sve do tada odigrane karte i njihov redoslijed.
- Tko je osvojio svaki završeni štih.
- Dotadašnji rezultat i javno dostupne bodove tekućeg dijeljenja.

Ne zna partnerove ni protivničke neotkrivene karte.

Engine pri preporučivanju poteza smije koristiti samo te informacije i zaključke koji iz njih proizlaze.

## 19. Zahtjevi za dosljednu implementaciju

### 19.1. Redoslijed obračuna dijeljenja

1. Utvrditi bodove karata i broj osvojenih štihova svakog para.
2. Dodati 10 bodova paru koji je osvojio posljednji štih.
3. Ako je jedan par osvojio svih osam štihova, dodati mu 90 bodova za štiglju.
4. Priznati obična zvanja samo paru koji je osvojio pravo na njih i barem jedan štih. Pravodobno najavljenu belu priznati njezinu paru samo ako je osvojio barem jedan štih.
5. Zbrojiti tako priznate bodove obaju parova u ukupnu vrijednost T. Nepriznata zvanja ne ulaze u T.
6. Provjeriti ima li par koji je zvao strogo više od T / 2. Ako nema, sve bodove T upisati protivnicima, a paru koji je zvao nulu.
7. Dodati konačni upis ukupnom rezultatu partije i provjeriti pobjedu prema odjeljku 16.

Trenutačna pobjeda belotom obrađuje se kao poseban završetak partije, izvan redovnog obračuna dijeljenja.

### 19.2. Odvajanje stvarnog stanja od znanja igrača

Simulator može sadržavati sve četiri ruke, ali preporuka određenom igraču smije dobiti samo njegov dopušteni pogled na stanje iz odjeljka 18. Skriveni talon, partnerove karte i protivničke karte ne smiju se izravno koristiti za preporuku dok nisu zakonito otkriveni.

Izostanak boje ili jače karte može se zaključivati iz odigranih poteza i obveza iz odjeljka 10. Takvi zaključci moraju ostati dosljedni cjelokupnoj povijesti igre. Protivnička odluka da kaže dalje predstavlja informaciju za procjenu, ali sama po sebi nije dokaz da određenu kartu nema.

### 19.3. Rangiranje preporuka

Engine treba razmatrati samo legalne poteze. Za svaki kandidat treba jasno razlikovati procjenu vjerojatnosti osvajanja štiha, prolaza ili rušenja u dijeljenju i pobjede u partiji. Te veličine nisu zamjenjive.

Budući da se traži uvažavanje ukupnog rezultata, cilj budućeg sustava preporuka je rangirati poteze prema procijenjenoj vjerojatnosti pobjede našeg para u partiji. To je zahtjev za engine, a ne dodatno pravilo igre. Procjene ovise o modelu skrivenih karata i budućih odluka igrača; nisu zajamčene objektivne vjerojatnosti. Izbor algoritma i načina procjene pripada naknadnoj razradi frameworka.

### 19.4. Primjeri za provjeru implementacije

- Bez zvanja: 81 : 81 znači pad para koji je zvao; konačni upis je 0 : 162 iz njegove perspektive.
- Bez zvanja: 82 : 80 znači prolaz; konačni upis ostaje 82 : 80.
- S ukupno 50 priznatih bodova zvanja: T = 212 i za prolaz treba najmanje 107 bodova.
- Štiglja bez zvanja: pobjednički par upisuje 252, drugi par 0.
- Pravodobno najavljena bela para bez ijednog štiha ne donosi bodove i ne povećava T.
- Pet karata do asa pobjeđuje šest do kralja u usporedbi nizova vrijednih 100 bodova.
- Kada je neadutska početna boja već presječena adutom, igrač koji je ima mora pratiti boju, ali ne mora nadjačati njezinu najjaču kartu.
- Kada igrač nema početnu boju, mora adutirati i nadjačati najjači adut ako može, čak i ako partner nosi štih.
- Točno 1000 nije pobjeda; jednak rezultat obaju parova iznad 1000 vodi u dodatno dijeljenje.

## 20. Izvor i potvrde varijante

Polazni tekst: korisnikova specifikacija Pravila hrvatske bele za četiri igrača. Dopune potvrđene u razgovoru 23. listopada 2026. uključuju dodatno dijeljenje kod izjednačenja iznad 1000, trenutačnu pobjedu belotom, poredak četiriju jednakih karata vrijednih 100, usporedbu nizova iste bodovne vrijednosti po završnoj karti, postupak najave i pokazivanja zvanja te obvezno nadjačavanje aduta.

Izvor osnovnih pravila naveden u polaznoj specifikaciji: hrvatska Wikipedija, Belot, https://hr.wikipedia.org/wiki/Belot, inačica https://hr.wikipedia.org/w/index.php?title=Belot&oldid=7230117. Polazni tekst prepričan je i prilagođen specifikaciji enginea; izvorni članak dostupan je pod licencijom CC BY-SA. Za implementaciju se primjenjuju pravila ovog dokumenta, uključujući dogovorene izmjene.

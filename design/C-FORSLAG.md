# Översyn C — förslag efter v4.0

Statusen nedan är avstämd mot koden i `src/dpt2/` efter att v4-backloggen
genomförts (Rail visar v4.0). Ingenting här är byggt — det här är underlag för
Stigs beslut om vad som ska in i en v4.1.

Handoffens utfall: **Kanske** = Fb1, N1, N3, T2 · **Nej** = Fb3, N2, T3.

---

## Avförda — behöver inget beslut

**T2 · Separat Snabbgallring-vy.** Utgick automatiskt när F1 genomfördes: Gallra
är nu ett kort med lägesväxeln AI/Snabb/Rapport. Ingen separat vy finns kvar.
**Klar, stryk från listan.**

**Fb3 · "Senast synkad"-tid** och **N2 · Batch-publicering** och **T3 ·
Testläge-banner** — Stig sa nej. Noterat, inget mer.

En anmärkning om T3 ändå: `Testläge`-switchen och `mock`-brickan ligger båda i
topbaren och syns i skarp app. Om de någonsin ska döljas är det en rad i
`App.svelte` (`{#if ARMOCK}`), inte ett projekt. Nämns bara så det inte
återupptäcks som en bugg senare.

---

## Fb1 · "Delvis publicerad" som eget statusläge — **rekommenderas**

Den enda av Kanske-punkterna som täpper en verklig lucka, och den är billig.

Idag räknar `Matcher.svelte:62` ut tonen så här:

```js
const tona = (rader) => rader.some((x) => x.status === 'publicerad') ? 'ok'
  : rader.length ? 'draft' : 'neutral'
```

`some()` betyder att **ett** publicerat inlägg färgar chippet grönt även om tre
andra kanaler ligger kvar som utkast. Raden ljuger alltså i precis det läge man
mest behöver veta sanningen: mitt i en publiceringsomgång.

Åtgärd: lägg till ett `delvis`-läge när raderna innehåller *både* publicerat och
opublicerat, och måla det gult. Färgen finns redan — `synk.js` har
`vantar: #E0A341` — och `Hornmarkor` tar godtycklig färg, så det är samma
visuella språk som A2 istället för en ny signal.

Omfattning: en funktion i `Matcher.svelte`, plus samma trestegs-logik i
`MatchHuvud.svelte` som har egna `kpill`-brickor. Ingen datamodell, ingen
migrering. Uppskattning: en kort session.

---

## N3 · Enkel publiceringsöversikt — **rekommenderas villkorat**

Datan finns redan: `some_material` (kanal + status) och `innehall`
(`publicerad` / `synkad_tid`). En "X publicerade per kanal och månad" går att
härleda utan att lagra något nytt — ungefär som `navChips` redan gör per match,
fast aggregerat.

Villkoret: det behöver en **plats**. Appen har ingen startsida — Rail går rakt
in i Fotojobb. Antingen bygger man den som ett kort överst i Matchpublicering
(billigt, men fel ställe för en global lägesbild), eller så är det egentligen
"ge DPT en startvy", vilket är ett större beslut än N3 självt.

Min rekommendation: **vänta**. Bygg den när/om en startvy blir aktuell, annars
blir det ett kort som ingen hittar.

---

## N1 · Sparade fraser & hashtag-set per kanal — **avråds i nuläget**

Tanken är rimlig, men den krockar med det som faktiskt byggdes i B2. Bildsvepet
genererar numera hashtags och @-omnämnanden enligt en låst regel i
`bildsvep.py`: exakt 5 hashtags, exakt 5 @-omnämnanden, `@nikonsverige` alltid
sist, osäkra handles märks med `?`. Ett bibliotek med sparade set skulle antingen
kringgå den regeln eller dubblera den.

Om problemet är "Claude gissar fel handle varje gång" är den träffsäkra
åtgärden en annan: **cacha verifierade @-handles på laget** (`lag.instagram`
finns redan i schemat) och skicka in dem som kända fakta i prompten, precis som
resultat och målskyttar redan skickas. Då försvinner `?`-markeringarna för lag
Stig fotograferar ofta, utan något nytt UI alls.

Föreslår att N1 skrivs om till: *"skicka lagens kända IG-handles till Bildsvepet
som verifierade fakta"*. Det är mindre arbete och löser den faktiska smärtan.

---

## Fb2 · Riktiga lag-loggor — inte kodarbete

Mekaniken finns hela vägen: logga-slot i Lag-editorn, `object-fit: contain`,
fallback till färgade initialer, och `loggacache.js` levererar data-URI:er.
Det som saknas är **filerna**. Ingen ny kod — Stig laddar upp loggorna via
logga-slotten i Lag-editorn så syns de i Aktiv match, Matchdag, SoMe och render.

---

## Vad jag skulle göra härnäst, i ordning

1. **Fb1** — billig, rättar en rad som just nu visar fel status.
2. **Fb2** — ingen kod, bara loggfiler; störst visuell effekt per minut.
3. **N1 omskriven** — cacha verifierade IG-handles på laget, mata in i prompten.
4. **N3** — vänta på att startvyn blir en fråga.

Och en punkt som inte kom från Översyn C men som föll ut ur v4-arbetet:
**§3 punkt 2** (notering/kund som andra rad på fotojobb-raden) är fortfarande
obyggd eftersom fotojobb-modellen saknar ett notering-fält. Det kräver ett
beslut om var texten ska bo — Google Calendars `description`, eller ett eget
lokalt fält som inte synkas. Se `project-dpt-v4`-minnet.

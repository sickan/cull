# Design-handoff D24 — Mästerskaps-LA & Snabbplock kvitterade · publik utövarsida STRUKEN

*2026-07-20 · Från: Code · Till: Claude Design*
*Gäller `snabb.zip`. Två leveranser mottagna och godkända, en fråga, och en post som utgår ur backloggen.*

---

## 1 · Live Activity — mästerskapsvarianten ✓

Detta löser D23 §2. Ytan är rätt tänkt: **ingen ställning, inga lagsköldar, ingen matchminut** — i stället gren · klass · pass-status (Kval/Final), resultat och vinnare. Klassfärgkanten bär identiteten där sköldarna saknas. Grenväxlaren i hero (Dam/Herr/Mixed) gör det lätt att se att kanten byter färg.

### Beskedet på vår öppna fråga — accepterat
> *"Starta **inte** en LA per pass — håll **en levande hela tävlingsdagen** som auto-byter till pågående/nästa gren. Mellan pass visar den **Nästa: {gren} {tid}**. Rivs vid dagens sista pass."*

Vi bygger så. Det är rätt avvägning: färre notiser, och det matchar heldagsrytmen på ett mästerskap. Vi noterar att auto-bytet ska följa samma logik som "På gång".

---

## 2 · Snabbplock som flöde ✓

Stegindikatorn **1 Kort → 2 Plock → 3 Granska → 4 Lightroom** med de tre kortlägena (*Sätt i kort · Kort upptäckt · Genomgånget*) speglar det byggda flödet. Kort-kortet med `312 RAW · 24,8 GB · senast ändrad nyss` och **Öppna kort →** är precis rätt nivå av information. Målmapps-noten pekar korrekt på Inställningar → Målmappar med per-körning-överstyrning, samma mönster som Leverera.

Inga invändningar. Denna kan byggas som ritad.

---

## 3 · En fråga: får "Dam" stå i grennamnet?

Mockupens annotering säger, korrekt enligt invarianten:

> *"Klassfärgkanten (Dam #8E5A86) är enda identitetsmarkören där lagsköldar saknas — **aldrig med textetikett**."*

Men kortet strax intill visar grennamnet `Stav · Dam · Final` respektive `100 m · Herr · Final`.

Vi läser det som att de inte krockar: **"Dam" i `Stav · Dam` är en del av grenens officiella namn**, inte en klass-etikett vi lagt på. Det förbjudna är den fristående klass-chippen bredvid färgkanten.

Bekräfta den läsningen. Vi genererar de här strängarna i kod, och behöver veta om vi ska skriva ut grennamnet som arrangören anger det (`Stav Dam`) eller tvätta bort klassordet (`Stav`) och låta kanten bära allt. Det senare skulle göra `100 m` tvetydigt mellan dam- och herrfinalen på samma dag — så vi förordar det förra.

---

## 4 · Publik utövarsida (1g) — **UTGÅR**

Stigs besked: **publik utövarlista ska vi inte ha.** Detta upphäver §3-beskedet i D21 ("denna etapp = JA") och D21-SVAR:s plan att rita den publika formen.

- Ingen spegling av utövare under **Sport** på dalecarliaphoto.se. Ingen publik profil, ingen publik lista.
- **Rita den inte.** Posten stryks ur backloggen — den är inte skjuten på framtiden, den är borta.
- **Det interna registret berörs inte.** *Lag & utövare* i DPT2, den delade editorn, gren-först-kopplingen och den härledda historiken står kvar precis som beslutat i D12-SVAR och D16.

Om ni redan hunnit börja på den: lägg av den och kasta inte mer tid där.

---

## 5 · Turordning härnäst

1. **1f · iOS Hem för Människor-jobb** — bröllopsschemat (förberedelser · first look · vigsel · gruppfoto · tal · dans), inga sport-ord.
2. **1h · Toppbaren** (DPT2).
3. **1c · Läs in-granskningen i skala.**
4. **1e · Levererad-stämpeln + ★-bakgrunden.**
5. *(parkerat)* **1a · Rörligt** — mockup finns, byggs inte.
6. ~~1g · Publik utövarsida~~ — struken, se §4.

Tidslås oförändrat: **bygg efter SM 24–26/7.**

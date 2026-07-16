# Bugg: Slug-byte vid ompublicering lämnar dubbletter på hemsidan

**Område:** DPT2 ↔ content-sync (publiceringskedjan)
**Prio:** Medel (drabbar sajten synligt, men går att städa manuellt)
**ID i backloggen:** BUG-10

## Problem

När en publicerad post döps om i DPT2 och ompubliceras får den ny slug + nytt id.
Workerns self-healing (`upsertContent` i `content-sync/src/db.ts`) rensar bara
dubbletter med samma (typ, slug) — den gamla raden blir kvar föräldralös i live-D1
och visas som dubblettkort på sajten.

**Inträffade 2026-07-16:** tre kvarlämnade versioner av samma fotografering låg
publika under Människor (`livsstilsportratt-vid-luftkastellet`, `wilson-blade-v9`,
`kvallsrundan`). Städades manuellt direkt i D1 + ombyggnad triggad.

## Önskat beteende

Omdöpning + ompublicering ska aldrig lämna kvar den gamla versionen på live.

## Trolig rot / var man börjar

- DPT2 skapar nytt id/slug vid ompublicering i stället för att återanvända
  befintligt id — kolla `src/dpt2/tjanster/innehall_synk.py` och hur editorn
  trådar id vid publicering.
- Alternativt: "reconciling publish" (städar rader som inte finns lokalt)
  körs inte för event-typen.

## Anteckningar

- Direkt-DELETE i D1 triggar ingen deploy-hook — sajten byggs bara om via
  workerns API-vägar (PUT/DELETE `/api/innehall/...`).
- R2-bilder under gamla slugen ska INTE raderas vid städning — nya posten
  kan referera dem i frontmatter.

## Klart när

- [ ] Omdöpt + ompublicerad post ersätter den gamla på live (ingen föräldralös rad)
- [ ] Tester som täcker omdöpningsfallet
- [ ] Ev. engångsstädning av kvarvarande föräldralösa rader i D1

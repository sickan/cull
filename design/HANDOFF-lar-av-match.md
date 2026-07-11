# Handoff: Lär av match (träning)

**Status:** Backend-klar, väntar på UI-design  
**Backend-funktion:** `api.lar_av_match(urval_id)`  
**Syftet:** Märka ett Photo Mechanic-gallrat urval som träningsdata för AI-modellen

## Vad gör det?

När fotografen väljer ett urval (från Gallra eller eget gallrat i Photo Mechanic) och klickar "Lär av match", systemet:
1. Läser de utvalda bildfilerna från urvalets mapp
2. Märker dem som träningsdata för nästa AI-gallring

Det är feedback-loop för AI-modellen — varje gång fotografen gallrar en match manual, lär systemet sig vad som är bra för just denna fotografs stil.

## Var bör det bo i UI?

**Förslag:** 
- Egen panel i "EFTER MATCH" (efter Matchpublicering) — liknande Snabbplock/Upprätning
- **Eller:** Knapp i Leverera-panelen (tillsammans med "Läs nummer")
- **Eller:** Knapp i Gallra (efter körningen är klar)

## UI-spec (baseline)

**Panel-namn:** "Träna" eller "Lär av match"

**Layout:**
- Titel + beskrivning
- Urval-väljar (dropdown: gallrade urval från denna match)
- En status-rad (t.ex. "12 bilder märkta som träningsdata")
- En körknapp

**Körknapp:** "Lägg till som träningsdata" eller "Märk och lär"

**Returvärde från backend:**
```json
{
  "ok": true,
  "antal": 47,
  "meddelande": "47 bilder märkta som träningsdata — AI lär av denna gallring."
}
```

## Koppling till övriga flöden

- **Gallra:** Efter en AI-gallring kan fotografen omedelbar klicka "Lär av match" för feedback
- **Photo Mechanic:** Om fotografen gallrar manuellt i PM, kan hen välja egna urvalet → "Lär av match"
- **Träna-panel (System):** Möjlig integrationspunkt senare för att se träningshistorik

---

**Backend-kod:** `src/dpt2/app.py:1204–1216` (`lar_av_match`)  
**Motsvarar v1:** `dpt.core.kor_gallring(rapport=True, laruppmanning=True)`

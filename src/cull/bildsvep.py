"""Genererar "Bildsvepet"-bildtext för Instagram i Dalecarlia Photos egen stil.

Hämtar matchfakta via Claude web search (resultat, målskyttar/nyckelhändelser,
tabellkontext, nästa match) → skriver ett EGET, omskrivet svenskt referat och
sätter ihop hela bildsvep-texten enligt fotografens mall: rubrik, matchrad,
länkrad, referat, "Nästa uppdrag", 5 hashtags och 5 @-omnämnanden.

Återger ALDRIG källornas formuleringar (bara fakta). Osäkra @-handles markeras
med '?' så fotografen kan verifiera innan posting. Texten POSTAS inte härifrån —
den visas för granskning/redigering och kopiering.
"""

import json
import os
import re

MODELL = "claude-opus-4-8"
WEBB_VERKTYG = {"type": "web_search_20260209", "name": "web_search", "max_uses": 6}
LANKRAD = "📸 Fler bilder → www.dalecarliaphoto.se/sport"

# Fotografens egna inlägg — STILMALL (matcha ton/format, inte fakta).
STILEXEMPEL = """\
⚽ BILDSVEPET

Malmö FF–Växjö DFF 3–0 (2–0) · OBOS Damallsvenskan · Eleda Stadion · 31 maj 2026

📸 Fler bilder → www.dalecarliaphoto.se/sport

MFF tog kommandot tidigt och Nellie Lilja sköt in 1–0 från distans innan Izzy D'Aquila ökade på till 2–0 före paus. Nathalie Hoff Persson stänkte dit 3–0 i den 72:a minuten, vilket lyfte Malmö till en fjärdeplats i tabellen medan Växjö ligger kvar i botten.

Nästa uppdrag 📸 Sverige U23 Dam–Norge · Landskamp · Fredriksskans Arena, Kalmar · onsdag 3 juni 18.30. Lagen möttes senast i april, där Sverige vann med 1–0, nu får Norge snabb revanschchans.

#MalmöFF #Damallsvenskan #sportfoto #växjödff #Bildsvepet

@malmo_ff @vaxjo_dff @obosdamallsvenskan @svenskfotboll @nikonsverige
---
BILDSVEPET ⚽

Malmö FF–Halmstads BK 5–2 (2–2)
Allsvenskan · Eleda Stadion · 30 maj 2026

📸 Fler bilder → www.dalecarliaphoto.se/sport

Adrian Skogmar prickade in ledningen redan efter fyra minuter, men Omar Faraj svarade med två snabba mål och vände till gästernas fördel innan Kenan Busuladžić nickade in 2–2 före paus. Andra halvlek tillhörde Erik Botheim, som på åtta minuter slog till med ett fullständigt hattrick och avgjorde till 5–2. Segern bröt MFF:s tunga svit och var precis vad laget behövde.

Nästa uppdrag 📸 Malmö FF dam–Växjö DFF · Damallsvenskan · Eleda Stadion · 31 maj 2026. Viktig match för Malmö FF för att hänga på topplagen!

#MalmöFF #Allsvenskan #sportfoto #svenskfotboll #Bildsvepet

@malmo_ff @halmstadsbollklubb @allsvenskan @svenskfotboll @nikonsverige
---
BILDSVEPET | Baltiska Hallen
Fler bilder finns på Dalecarlia Photo www.dalecarliaphoto.se/sport 📷🔗

SM-finalen är säkrad 🤾‍♂️
HK Malmö har slagit ut IK Sävehof och är klara för SM-final. En sån där kväll där det är lite svårt att ta in vad som händer medan det händer.

Det svängde, det var tajt, och det var mycket nerver i luften. Men Malmö stod kvar när det skulle avgöras, tog de viktiga räddningarna, satte de avgörande bollarna och lät Baltiska göra resten. Slutresultat 37–34 och nu väntar final.

#handboll #slutspel #hkmalmö #sävehof #baltiskahallen

@hkmhandboll @ik_savehof @handbollsligan_herr @svenskhandboll.officiell @nikonsverige"""

SYSTEM = (
    "Du skriver 'Bildsvepet'-bildtexter för Instagram åt sportfotografen Dalecarlia "
    "Photo, på svenska. Använd web search för att hitta matchfakta: resultat och "
    "halvtid/set, målskyttar/poänggörare och nyckelhändelser, tabell- eller "
    "sammanhangskontext, och gärna lagets nästa match. Skriv ett EGET, omskrivet "
    "referat — återge ALDRIG källornas formuleringar, bara fakta. Hitta aldrig på "
    "resultat, namn eller händelser.\n\n"
    "FORMAT (följ fotografens stil i exemplen exakt):\n"
    "1. Rubrikrad: en sport-emoji + 'BILDSVEPET' (⚽ fotboll, 🤾 handboll, 🏐 volleyboll).\n"
    "2. Matchrad: 'Hemma–Borta resultat (halvtid/set) · Liga · Arena · datum på "
    "svenska'. Tankstreck '–' mellan lagen och i resultat; ' · ' som avgränsare.\n"
    f"3. Länkrad: '{LANKRAD}'.\n"
    "4. Referat: 2–4 meningar. NAMNGE målskyttarna/poänggörarna och i vilken ordning/"
    "minut målen kom när det framgår av källorna — det är kärnan i stilen (t.ex. "
    "'X sköt in 1–0 ... innan Y ökade på'). Lägg till tabell-/sammanhangskontext. "
    "Sök vidare specifikt efter målskyttar om första sökningen inte ger dem. "
    "Journalistisk men personlig och varm ton.\n"
    "5. 'Nästa uppdrag 📸 nästa match · tävling · arena · datum tid. <en mening "
    "teaser>' — bara om du hittar lagets nästa match; annars utelämna raden.\n"
    "6. Exakt 5 hashtags, blanda lag/liga/sport + #sportfoto, avsluta med #Bildsvepet.\n"
    "7. Exakt 5 @-omnämnanden på sista raden: hemmalag, bortalag, liga, förbund, "
    "@nikonsverige (alltid sist). Sök upp lagens/ligans/förbundets OFFICIELLA "
    "Instagram-handles. Är du INTE säker på en handle, skriv den med '?' först "
    "(t.ex. @?malmo_ff). Gissa ALDRIG en enskild spelares konto.\n\n"
    "Svara med JSON: {\"referat\": \"...endast referattexten...\", "
    "\"bildsvep\": \"...hela bildtexten enligt formatet ovan...\"}.\n\n"
    "STILMALL (matcha ton och format, INTE fakta):\n" + STILEXEMPEL
)


def tillganglig():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except Exception:
        return False


def _parsa(text):
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def generera(matchinfo, sport="", hemma_farg="", logg=print):
    """Returnerar {referat, bildsvep} eller None."""
    matchinfo = (matchinfo or "").strip()
    if not matchinfo:
        logg("⚠ Ingen matchinfo angiven.")
        return None
    if not tillganglig():
        logg("⚠ ANTHROPIC_API_KEY eller anthropic saknas.")
        return None

    import anthropic
    klient = anthropic.Anthropic(max_retries=4)
    fraga = f"Match: {matchinfo}."
    if sport and sport.lower() != "auto":
        fraga += f" Sport: {sport}."
    if hemma_farg:
        fraga += f" Hemmalaget (det fotografen följt) spelar i {hemma_farg}."
    fraga += "\nSkriv Bildsvepet enligt formatet och svara med JSON."

    messages = [{"role": "user", "content": fraga}]
    logg("Hämtar matchfakta och skriver Bildsvepet via Claude (web search)…")
    svar = None
    try:
        for _ in range(4):
            svar = klient.messages.create(
                model=MODELL, max_tokens=4000, system=SYSTEM,
                tools=[WEBB_VERKTYG], messages=messages)
            if svar.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": svar.content})
                continue
            break
    except Exception as e:
        logg(f"⚠ Misslyckades: {type(e).__name__}: {e}")
        return None

    if svar is None or svar.stop_reason == "refusal":
        logg("⚠ Inget svar.")
        return None
    text = "".join(b.text for b in svar.content if b.type == "text")
    data = _parsa(text)
    if not data or not data.get("bildsvep"):
        logg("⚠ Kunde inte tolka svaret.")
        return None
    logg("✓ Bildsvepet klart. Granska, verifiera @-handles, kopiera.")
    return data

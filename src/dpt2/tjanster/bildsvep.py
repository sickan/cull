"""Bildsvepet — Instagram-bildtext i Dalecarlia Photos egen stil, ovanpå
Claude-tjänsten.

Tunn konsument: bygger SYSTEM-prompt + fråga och delegerar till
dpt2.tjanster.claude.fraga_json med web_search. Hämtar matchfakta (resultat,
målskyttar/nyckelhändelser, tabellkontext, nästa match) och skriver ett EGET,
omskrivet svenskt referat enligt fotografens mall. Prompt/stilmall migrerade
verbatim ur gamla dpt.bildsvep (DATA). Klienten kan injiceras (test); utelämnad
→ tjänsten skapar en skarp klient.

Texten POSTAS aldrig härifrån — den visas för granskning/redigering/kopiering.
Osäkra @-handles markeras med '?' så fotografen kan verifiera innan posting.
"""

from dpt2.tjanster import claude

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
    "Photo, på svenska. Frågan innehåller KÄNDA MATCHFAKTA (resultat, halvtid/set, "
    "arena, datum, liga, målskyttar) hämtade direkt ur fotografens egen matchdatabas "
    "— dessa är REDAN VERIFIERADE. Använd dem rakt av, sök INTE efter dem och "
    "motsäg dem ALDRIG. Använd web search bara för det KÄNDA MATCHFAKTA inte täcker: "
    "nyckelhändelser/spelförlopp (om målskyttar saknar minuter/sammanhang), tabell- "
    "eller sammanhangskontext, lagets nästa match, och lagens/ligans OFFICIELLA "
    "Instagram-handles. Skriv ett EGET, omskrivet referat — återge ALDRIG källornas "
    "formuleringar, bara fakta. Hitta ALDRIG på resultat, namn eller händelser; "
    "saknas en uppgift (även efter sökning) — utelämna den eller den raden hellre "
    "än att gissa.\n\n"
    "FORMAT (följ fotografens stil i exemplen exakt):\n"
    "1. Rubrikrad: en sport-emoji + 'BILDSVEPET' (⚽ fotboll, 🤾 handboll, 🏐 volleyboll).\n"
    "2. Matchrad: 'Hemma–Borta resultat (halvtid/set) · Liga · Arena · datum på "
    "svenska'. Tankstreck '–' mellan lagen och i resultat; ' · ' som avgränsare. "
    "Dessa fält kommer direkt ur KÄNDA MATCHFAKTA — skriv dem ordagrant, hitta "
    "aldrig egna varianter.\n"
    f"3. Länkrad: '{LANKRAD}'.\n"
    "4. Referat: 2–4 meningar. NAMNGE målskyttarna/poänggörarna (redan givna i "
    "KÄNDA MATCHFAKTA om de finns där) och i vilken ordning/minut målen kom — det "
    "är kärnan i stilen (t.ex. 'X sköt in 1–0 ... innan Y ökade på'). Lägg till "
    "tabell-/sammanhangskontext via websökning. Journalistisk men personlig och "
    "varm ton.\n"
    "5. 'Nästa uppdrag 📸 nästa match · tävling · arena · datum tid. <en mening "
    "teaser>' — bara om du hittar lagets nästa match via websökning; annars "
    "utelämna raden.\n"
    "6. Exakt 5 hashtags, blanda lag/liga/sport + #sportfoto, avsluta med #Bildsvepet.\n"
    "7. Exakt 5 @-omnämnanden på sista raden: hemmalag, bortalag, liga, förbund, "
    "@nikonsverige (alltid sist). Sök upp lagens/ligans/förbundets OFFICIELLA "
    "Instagram-handles. Är du INTE säker på en handle, skriv den med '?' först "
    "(t.ex. @?malmo_ff). Gissa ALDRIG en enskild spelares konto.\n\n"
    "Svara med JSON: {\"referat\": \"...endast referattexten...\", "
    "\"bildsvep\": \"...hela bildtexten enligt formatet ovan...\"}.\n\n"
    "STILMALL (matcha ton och format, INTE fakta):\n" + STILEXEMPEL
)


def _klient_eller_skapa(klient, logg):
    if klient is not None:
        return klient
    if not claude.tillganglig():
        logg("⚠ ANTHROPIC_API_KEY eller anthropic saknas.")
        return None
    return claude.ny_klient()


# B2: ton-val i Matchpublicering — styr formuleringen, inte fakta.
TON_INSTR = {
    "Neutral": "Håll en neutral, saklig ton.",
    "Peppig": "Håll en peppig, energisk ton — men trovärdig, överdriv inte.",
    "Kort": "Håll bildtexten kort och koncis — bara det viktigaste.",
}


def bygg_fraga(matchinfo, *, sport="", hemma_farg="", resultat="", mellan="",
               malskyttar="", arena="", datum="", liga="", ton=""):
    """Bygger frågesträngen som skickas till Claude — en ren strängoperation,
    inget nätverksanrop. Utbruten ur generera() så UI:t kan visa EXAKT vad som
    kommer skickas (för godkännande) innan det skarpa, ~2 minuter långa
    anropet görs. De redan kända matchfakta (resultat/mellan/målskyttar/arena/
    datum/liga — allt appen redan har lokalt via resultat-remsan/matchposten)
    skickas med rakt av så Claude inte behöver websöka efter sånt som redan
    är verifierat; websökning används bara för sådant appen INTE har (nästa
    match, tabellkontext, @-handles)."""
    matchinfo = (matchinfo or "").strip()
    fraga = f"Match: {matchinfo}."
    if sport and sport.lower() != "auto":
        fraga += f" Sport: {sport}."
    if hemma_farg:
        fraga += f" Hemmalaget (det fotografen följt) spelar i {hemma_farg}."
    kanda = []
    if resultat:
        kanda.append(f"Resultat: {resultat}")
    if mellan:
        kanda.append(f"Halvtid/set: {mellan}")
    if malskyttar:
        kanda.append(f"Målskyttar: {malskyttar}")
    if arena:
        kanda.append(f"Arena: {arena}")
    if datum:
        kanda.append(f"Datum: {datum}")
    if liga:
        kanda.append(f"Liga: {liga}")
    if kanda:
        fraga += ("\n\nKÄNDA MATCHFAKTA (redan verifierade av fotografen, "
                  "använd rakt av — sök inte efter dessa):\n" + "\n".join(kanda))
    if ton and ton in TON_INSTR:
        fraga += "\n\n" + TON_INSTR[ton]
    fraga += "\nSkriv Bildsvepet enligt formatet och svara med JSON."
    return fraga


def generera(matchinfo, *, sport="", hemma_farg="", resultat="", mellan="",
             malskyttar="", arena="", datum="", liga="", ton="", logg=print, klient=None):
    """Returnerar {referat, bildsvep} eller None. matchinfo = matchrad/-sträng;
    övriga kwargs ger kontext/kända matchfakta (se bygg_fraga). Klienten
    injiceras i test."""
    if not (matchinfo or "").strip():
        logg("⚠ Ingen matchinfo angiven.")
        return None
    klient = _klient_eller_skapa(klient, logg)
    if klient is None:
        return None

    fraga = bygg_fraga(matchinfo, sport=sport, hemma_farg=hemma_farg, resultat=resultat,
                       mellan=mellan, malskyttar=malskyttar, arena=arena, datum=datum,
                       liga=liga, ton=ton)

    logg("Hämtar matchfakta och skriver Bildsvepet via Claude (web search)…")
    data = claude.fraga_json(klient, SYSTEM, fraga,
                             verktyg=claude.web_search_verktyg(), logg=logg)
    if not data or not data.get("bildsvep"):
        logg("⚠ Kunde inte tolka svaret.")
        return None
    logg("✓ Bildsvepet klart. Granska, verifiera @-handles, kopiera.")
    return data

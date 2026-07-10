# Koppla privata kalendrar till Google — engångssetup

DPT2 läser dina privata kalendrar **skrivskyddat, direkt från Macen** (aldrig via
Cloudflare-Workern — den äger bara jobbkalendern). För det behöver appen en egen
**OAuth-klient av typen Desktop**. Den skapar du en gång i Google Cloud Console.

Logga in i konsolen med **det konto som ser BÅDA kalendrarna** — alltså
`sjuab.se`-kontot (din + fruns delade kalender ligger där). Det är också det
kontot du sedan loggar in med i appen.

---

## 1. Projekt + API

1. Gå till <https://console.cloud.google.com/> (inloggad som `sjuab.se`).
2. Skapa ett projekt, t.ex. **"DPT privat kalender"** (eller återanvänd ett).
3. Aktivera **Google Calendar API**:
   APIs & Services → **Enable APIs and Services** → sök "Google Calendar API" → **Enable**.

## 2. OAuth-samtyckesskärm (consent screen)

APIs & Services → **OAuth consent screen**.

- **Om `sjuab.se` är Google Workspace** (troligt för en firmaadress) och du får
  välja **User type: Internal** → välj det. Då slipper du testanvändare,
  verifiering OCH problemet i rutan nedan. Detta är det bästa spåret.
- **Annars: External.** Fyll i appnamn + din e-post. Under **Scopes**, lägg till
  `.../auth/calendar.readonly`. Under **Test users**, lägg till din
  `sjuab.se`-adress.

> ⚠️ **Viktigt om du valde External:** så länge appen står i **Testing** går
> Google-tokens ut efter **7 dagar** → du måste logga in igen varje vecka. För
> att slippa det: gå tillbaka till OAuth consent screen och tryck **Publish app**
> (status → "In production"). Appen är overifierad, så du får en varningsruta
> ("Google hasn't verified this app") — klicka **Advanced → Go to … (unsafe)**.
> Det är ofarligt: det är din egen app, ditt eget konto, bara läsbehörighet.
> Med Internal finns inte det här problemet alls.

## 3. Skapa Desktop-klienten

APIs & Services → **Credentials** → **Create Credentials** → **OAuth client ID**.

- **Application type: Desktop app**  ← måste vara detta (loopback-inloggningen
  bygger på det; ingen redirect-URI behöver anges).
- Namn: valfritt, t.ex. "DPT desktop".
- **Create** → kopiera **Client ID** och **Client secret**.

## 4. Klistra in i appen

I DPT2: **Inställningar → Privata kalendrar** → klistra in Client ID + secret →
**Spara uppgifter** → **Logga in med Google**. En flik öppnas; godkänn med
`sjuab.se`. Fliken säger "Klart" och appen visar dina kalendrar. Bocka i vilka
som ska räknas som privata (din + fruns delade).

Klart. Inget lagras utom en refresh-token i `~/.config/dpt/privat_kalender.json`
— allt annat lever bara medan appen är öppen, och kalendrarna rörs aldrig av en
skrivning.

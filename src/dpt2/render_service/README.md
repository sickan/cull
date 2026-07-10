# dpt-render — molnrender av Horisont-storyn

Del av **Mobil Live Etapp 2**: publicera en story från läktaren när Macen ligger
avstängd i väskan. Telefonen laddar upp ett foto till R2, content-sync-workern
anropar den här servicen, och resultatet postas till Meta.

## Varför den finns (och varför den är så tunn)

Horisont har **exakt en implementation**: `dpt2/motorer/story_overlay.py`
(~1000 rader Pillow — 7 moment, 3 teman, 5 format, Saira, laglogotyper med
monogram-fallback). Det finns *ingen* HTML/CSS-version; designprototyperna är
mockuper. Att rendera i molnet med headless Chrome hade betytt att skriva om allt
pixeltroget och sedan underhålla två renderare som obönhörligt glider isär.

Den här servicen implementerar därför **ingen grafik alls**. Den importerar
`story_overlay` oförändrat och matar den med filer.

Skillnaden mot desktop-anropet är bara var bitarna kommer ifrån:

| | desktop | molnet |
|---|---|---|
| foto | disk (Lightroom-export) | R2 → base64 i requesten |
| laglogotyper | `~/.config/dpt/loggor` | R2 → base64 i requesten |

**Loggorna måste skickas med.** `story_overlay` slår annars upp dem i
`~/.config/dpt/loggor`, som inte finns i en container — resultatet blir tyst
monogram-fallback i stället för klubbmärket. `skapa_story` tar redan
`hem_logga`/`borta_logga` som explicita sökvägar, så renderaren behövde inte röras.
(Verifierat: en inskickad logga vinner över diskuppslaget.)

## API

Server-till-server. Servicen gör **inga utgående anrop** — den är en ren funktion
över HTTP, vilket gör den trivial att köra var som helst och trivial att testa.

```
GET  /health   → 200 {"ok": true}

POST /rendera  → 200 image/jpeg | 400 {"fel": …} | 401 | 500
     Authorization: Bearer $RENDER_API_KEY     (hoppas över om variabeln är tom)
     Content-Type: application/json
{
  "moment":     "slutresultat",        // krävs: avspark|halvtid|slutresultat|
                                       //        startelva|malgorare|nasta_match
  "lag_hemma":  "Malmö FF",            // krävs
  "lag_borta":  "Kristianstads DFF",   // krävs
  "foto":       "<base64 JPEG>",       // krävs

  "liga": "OBOS Damallsvenskan", "stallning": "3-1",
  "mal_rad": "Hansson 14', Ali 63'", "arena": "Eleda Stadion",
  "avspark_tid": "18:00", "next_when": "",
  "sport": "fotboll", "tema": "Hav",   // Hav|Sol|Rosé
  "gren": "dam",                       // dam|herr|mixed → färgad kant
  "format": "9x16",                    // 9x16|4x5|1x1|1.91x1|16x9
  "fokus": {"x": 50, "y": 35}, "zoom": 1.15,

  "hem_logga": "<base64 PNG>", "borta_logga": "<base64 PNG>"
}
```

Ogiltig indata (saknat foto, trasig JPEG, dålig base64, för stor bild) ger **400
med förklaring**, aldrig en tyst 500.

## Köra lokalt

```bash
RENDER_API_KEY=hemlig PORT=8090 PYTHONPATH=src python -m dpt2.render_service.server
curl -s localhost:8090/health
```

## Docker

```bash
docker build -f src/dpt2/render_service/Dockerfile -t dpt-render .   # från repots rot
docker run -p 8080:8080 -e RENDER_API_KEY=hemlig dpt-render
```

> Dockerfilen är skriven men **ännu inte byggd** — docker fanns inte i miljön där
> servicen togs fram. Kör bygget en gång innan den deployas.

## Tester

```bash
python -m pytest src/dpt2/render_service/ -q
```

15 tester mot den **riktiga** renderaren (en mock hade testat fel sak): format,
genomsläpp av matchdata, gren-kant, att inskickade loggor används, fokus/zoom,
felfallen, och att temp-filerna städas.

## Prestanda

1080×1920 renderas på ~180 ms lokalt (~230 ms över HTTP inkl. base64).

## Status

Byggd och verifierad lokalt. **Återstår:** ladda upp laglogotyperna till R2,
worker-orkestrering (`POST /api/live/:id/story`), PWA:ns publiceringsvy, och
Meta-postning från molnet.

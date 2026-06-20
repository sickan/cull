# cull

Teknisk culling av NEF-uppdrag på macOS.

Extraherar den inbäddade JPEG-previewen ur varje NEF-fil, poängsätter på
skärpa, exponering och ögon-detektion, grupperar burst-serier och kopierar
topp-urvalet till en undermapp `urval/`.

## Krav

```bash
brew install exiftool
```

## Installation

```bash
pip install -e /sökväg/till/cull
```

## Användning

```bash
# behåll 20 % (default)
cull "/sökväg/till/uppdrag"

# behåll exakt 30 bilder
cull "/sökväg/till/uppdrag" --topp 30

# behåll 15 %
cull "/sökväg/till/uppdrag" --andel 0.15

# poängsätt utan att kopiera
cull "/sökväg/till/uppdrag" --rapport

# burst-gräns 3 sekunder
cull "/sökväg/till/uppdrag" --burst-sek 3
```

## Hur det fungerar

1. Extraherar `JpgFromRaw` (eller `PreviewImage`) ur varje NEF med exiftool
2. Beräknar Laplacian-varians (skärpa) och exponeringspoäng på den nedskalade previewen
3. Detekterar ansikten och ögon med Haars kaskader — ger liten bonus
4. Grupperar bilder tagna inom `--burst-sek` sekunder av varandra
5. Väljer bästa bild per burst-grupp, kompletterar till önskat antal
6. Kopierar NEF (+ eventuell XMP sidecar) till `urval/`

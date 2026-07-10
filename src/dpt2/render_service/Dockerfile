# Molnrender för Horisont-storyn (Mobil Live, Etapp 2).
#
# Innehåller ingen egen grafikkod: den kör `dpt2.motorer.story_overlay`,
# samma renderare som desktop-appen. Enda tredjepartsberoendet är Pillow.
#
# Bygg från REPOTS ROT (contexten behöver src/):
#   docker build -f src/dpt2/render_service/Dockerfile -t dpt-render .
#   docker run -p 8080:8080 -e RENDER_API_KEY=... dpt-render
#
# Värd-agnostisk med flit: Cloudflare Containers (kräver wrangler 4.x),
# Fly, Railway eller en liten server — alla lyssnar bara på $PORT.

FROM python:3.12-slim

# Pillow laddar typsnitt/PNG via inbyggda wheels; inga apt-paket behövs för
# de format vi använder (JPEG/PNG + FreeType följer med manylinux-wheelen).
RUN pip install --no-cache-dir "Pillow>=10,<13"

WORKDIR /app

# Bara det renderaren faktiskt behöver — inte hela appen.
#   motorer/      story_overlay (renderaren)
#   data/         sportprofil (ren python; __init__ drar in sqlite3, stdlib)
#   assets/       Saira-typsnitten + temaloggorna
#   render_service/
COPY src/dpt2/__init__.py            /app/dpt2/__init__.py
COPY src/dpt2/motorer/               /app/dpt2/motorer/
COPY src/dpt2/data/                  /app/dpt2/data/
COPY src/dpt2/assets/                /app/dpt2/assets/
COPY src/dpt2/render_service/        /app/dpt2/render_service/

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PORT=8080

# Kör som icke-root; servicen skriver bara till tempkatalogen.
RUN useradd --create-home --uid 10001 render
USER render

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health').status==200 else 1)"

CMD ["python", "-m", "dpt2.render_service.server"]

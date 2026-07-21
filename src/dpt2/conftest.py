"""Testsäkerhet: nolla content-sync-nyckeln så INGEN test råkar nå produktion.

`lista_fotojobb` auto-synkar fotojobb till mobilen (best-effort nätanrop). En
default-`Api` läser `CONTENT_SYNC_API_KEY` ur env — och på en utvecklarmaskin
ligger den i skalet. Utan den här städningen skulle en test som anropar
`lista_fotojobb` (eller vilken synk som helst) kunna pusha mot den skarpa workern.
Live-testerna injicerar redan en FejkLiveSynk; det här skyddar allt annat.
"""
import os
import pytest


@pytest.fixture(autouse=True)
def _inga_skarpa_synkanrop(monkeypatch):
    # Alla tjänstenycklar nollas: koden faller genomgående tillbaka på
    # os.environ (`api_key or os.environ.get(...)`), så en nyckel i utvecklarens
    # skal läcker annars in i "utan-nyckel"-testerna (meta/bildhosting/kalender)
    # OCH riskerar skarpa anrop. Testerna injicerar egna fejk-transporter/nycklar.
    for var in ("CONTENT_SYNC_API_KEY", "CONTENT_SYNC_BASE_URL",
                "CALENDAR_SYNC_API_KEY", "CALENDAR_SYNC_BASE_URL",
                "DPT_BILD_API_KEY", "META_ACCESS_TOKEN", "IG_USER_ID"):
        monkeypatch.delenv(var, raising=False)

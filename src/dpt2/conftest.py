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
    monkeypatch.delenv("CONTENT_SYNC_API_KEY", raising=False)
    monkeypatch.delenv("CONTENT_SYNC_BASE_URL", raising=False)

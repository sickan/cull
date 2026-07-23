"""EN sanning för plats: fält/iOS-satta plats-overrides ska vävas in i
jobblistan INNAN wholesale-pushen — så en plats som fältet satt (för jobb utan
plats i Google Calendar) aldrig klampas över och speglas till alla klienter.

Testar `Api._vav_in_platsoverrides` isolerat mot en stub-live_synk (inget nät,
ingen DB): rätt jobb får platsen, en satt override VINNER över källans plats
(b0b253b: medvetet fält-val slår vag kalenderplats), tomt override-namn lämnar
källan orörd, koordinater fylls i, tom karta är en no-op, nätfel kastar aldrig.
"""

import unittest

from dpt2.app import Api


class StubSynk:
    def __init__(self, svar):
        self._svar = svar
        self.anrop = 0

    def hamta_jobbplats(self):
        self.anrop += 1
        if isinstance(self._svar, Exception):
            raise self._svar
        return self._svar


class Stub:
    """Minsta yta `_vav_in_platsoverrides` rör (self.live_synk + cache)."""

    def __init__(self, synk):
        self.live_synk = synk

    vav = Api._vav_in_platsoverrides


class TestVavInPlatsoverrides(unittest.TestCase):
    def _kor(self, karta, jobb):
        s = Stub(StubSynk({"jobb": karta}))
        s.vav(jobb)
        return s, jobb

    def test_jobb_utan_plats_far_overridens(self):
        jobb = [{"id": "j1", "location": ""}]
        _, ut = self._kor({"j1": {"namn": "Nöbbelöv kyrka", "lat": 55.7, "lon": 13.2}}, jobb)
        self.assertEqual(ut[0]["location"], "Nöbbelöv kyrka")
        self.assertTrue(ut[0]["plats_override"])
        self.assertEqual((ut[0]["lat"], ut[0]["lon"]), (55.7, 13.2))

    def test_override_vinner_over_kallans_plats(self):
        # b0b253b (Stig 22/7): en satt override är ett MEDVETET fält-val och
        # vinner över kalenderplatsen — "Nöbbelövs Kyrka" ersätter "Lund".
        # (Ersätter gamla test_jobb_med_egen_plats_rors_inte som vaktade
        # regeln FÖRE beslutet och blev stående rött efter v5.0-taggen.)
        jobb = [{"id": "j1", "location": "Lund, Sverige", "lat": 1.0, "lon": 2.0}]
        _, ut = self._kor({"j1": {"namn": "Nöbbelövs Kyrka", "lat": 9.0, "lon": 9.0}}, jobb)
        self.assertEqual(ut[0]["location"], "Nöbbelövs Kyrka")
        self.assertTrue(ut[0]["plats_override"])
        self.assertEqual((ut[0]["lat"], ut[0]["lon"]), (9.0, 9.0))

    def test_tomt_overridenamn_lamnar_kallans_plats(self):
        # Frånkopplings-guarden: tomt namn i overriden = ingen override —
        # källans plats och koordinat ska stå orörda.
        jobb = [{"id": "j1", "location": "Malmö IP", "lat": 1.0, "lon": 2.0}]
        _, ut = self._kor({"j1": {"namn": "  ", "lat": 9.0, "lon": 9.0}}, jobb)
        self.assertEqual(ut[0]["location"], "Malmö IP")
        self.assertNotIn("plats_override", ut[0])
        self.assertEqual((ut[0]["lat"], ut[0]["lon"]), (1.0, 2.0))

    def test_koordinat_fylls_nar_platsnamn_finns_men_koord_saknas(self):
        # location finns men lat/lon saknas → koordinaten ska ändå fyllas.
        jobb = [{"id": "j1", "location": "Arena", "lat": None, "lon": None}]
        _, ut = self._kor({"j1": {"namn": "Arena", "lat": 3.0, "lon": 4.0}}, jobb)
        self.assertEqual((ut[0]["lat"], ut[0]["lon"]), (3.0, 4.0))

    def test_tom_karta_ar_noop(self):
        jobb = [{"id": "j1", "location": ""}]
        _, ut = self._kor({}, jobb)
        self.assertEqual(ut[0]["location"], "")
        self.assertNotIn("plats_override", ut[0])

    def test_natfel_kastar_aldrig(self):
        s = Stub(StubSynk(RuntimeError("nätet nere")))
        jobb = [{"id": "j1", "location": ""}]
        s.vav(jobb)  # får inte kasta
        self.assertEqual(jobb[0]["location"], "")

    def test_cache_undviker_upprepade_anrop(self):
        synk = StubSynk({"jobb": {"j1": {"namn": "A", "lat": 1, "lon": 2}}})
        s = Stub(synk)
        s.vav([{"id": "j1", "location": ""}])
        s.vav([{"id": "j1", "location": ""}])
        self.assertEqual(synk.anrop, 1)  # andra gången ur cachen (~30 s)


class TestSynkAndringar(unittest.TestCase):
    """Realtids ändringskanal: första pollen sätter baslinje (inga 'ändrade'),
    därefter rapporteras bara domäner vars stämpel faktiskt rört sig."""

    def _api(self, svar):
        class SynkStub:
            def __init__(s): s.svar = svar; s.i = 0
            def hamta_andringar(s):
                v = s.svar[s.i] if s.i < len(s.svar) else s.svar[-1]
                s.i += 1
                return v
        s = Stub(None)
        s.live_synk = SynkStub()
        s.synk_andringar = Api.synk_andringar.__get__(s)
        return s

    def test_forsta_ar_baslinje(self):
        a = self._api([{"jobb": "t1", "idag": "t1", "jobbplats": "t1", "nu": "x"}])
        self.assertEqual(a.synk_andringar(), {"ok": True, "andrade": []})

    def test_andrad_doman_rapporteras(self):
        a = self._api([
            {"jobb": "t1", "idag": "t1", "jobbplats": "t1", "nu": "x"},
            {"jobb": "t1", "idag": "t1", "jobbplats": "t2", "nu": "y"},  # plats rörde sig
        ])
        a.synk_andringar()                       # baslinje
        self.assertEqual(a.synk_andringar()["andrade"], ["jobbplats"])

    def test_oforandrat_ger_inga(self):
        a = self._api([{"jobb": "t1", "idag": None, "jobbplats": None, "nu": "x"}])
        a.synk_andringar()
        self.assertEqual(a.synk_andringar()["andrade"], [])

    def test_natfel_ger_ok_false(self):
        a = self._api([{}])
        self.assertEqual(a.synk_andringar(), {"ok": False, "andrade": []})


if __name__ == "__main__":
    unittest.main()

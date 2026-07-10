"""Tester för worker-IPC: event-parsning + skarp demo-subprocess (stdlib, körs
överallt — ingen ML).

  python -m unittest dpt2.tjanster.test_korning -v
"""

import unittest

from dpt2.tjanster import korning
from dpt2 import worker


class TestParsaEvent(unittest.TestCase):
    def test_giltigt_event(self):
        ev = korning.parsa_event('{"typ": "progress", "andel": 0.5}')
        self.assertEqual(ev["typ"], "progress")
        self.assertEqual(ev["andel"], 0.5)

    def test_icke_json_blir_logg(self):
        ev = korning.parsa_event("UserWarning: nåt från ett bibliotek")
        self.assertEqual(ev["typ"], "logg")
        self.assertIn("UserWarning", ev["text"])

    def test_json_utan_giltig_typ_blir_logg(self):
        ev = korning.parsa_event('{"typ": "skräp", "x": 1}')
        self.assertEqual(ev["typ"], "logg")

    def test_tom_rad(self):
        self.assertIsNone(korning.parsa_event("  \n"))

    def test_event_rad_round_trip(self):
        rad = korning.event_rad(korning.event("logg", niva="ok", text="åäö"))
        self.assertEqual(korning.parsa_event(rad)["text"], "åäö")


class TestWorkerMain(unittest.TestCase):
    def setUp(self):
        self.rader = []
        self._orig = worker._emit
        worker._emit = lambda ev: self.rader.append(ev)

    def tearDown(self):
        worker._emit = self._orig

    def test_demo_event_sekvens(self):
        kod = worker.main(["demo", '{"steg": 3}'])
        self.assertEqual(kod, 0)
        typer = [e["typ"] for e in self.rader]
        self.assertEqual(typer[0], "start")
        self.assertEqual(typer[-1], "klar")
        self.assertEqual(sum(1 for t in typer if t == "progress"), 3)
        self.assertEqual(self.rader[-1]["resultat"]["steg"], 3)

    def test_okant_jobb(self):
        self.assertEqual(worker.main(["finns-inte"]), 2)
        self.assertEqual(self.rader[-1]["typ"], "fel")

    def test_gallra_utan_urval_id_ger_fel(self):
        worker.main(["gallra", "{}"])           # returnerar före modell-laddning
        self.assertEqual(self.rader[-1]["typ"], "fel")

    def test_nummer_utan_urval_id_ger_fel(self):
        worker.main(["nummer", "{}"])
        self.assertEqual(self.rader[-1]["typ"], "fel")

    def test_story_utan_moment_ger_fel(self):
        # db_path MÅSTE anges — utan den öppnade (och migrerade!) det här testet
        # användarens skarpa ~/.config/dpt2/dpt.db. Se worker._db.
        worker.main(["story", '{"config": {}, "db_path": ":memory:"}'])
        self.assertEqual(self.rader[-1]["typ"], "fel")

    def test_jobb_utan_db_path_ger_fel_och_ror_aldrig_skarpa_db(self):
        """Regressionsskydd: ett worker-jobb får ALDRIG falla tillbaka på
        db.DB_DEFAULT. Gjorde det tidigare → pytest migrerade den skarpa
        databasen och DPT2 vägrade starta."""
        from dpt2.data import db as _db_mod
        worker.main(["story", '{"config": {"moment": "avspark"}}'])   # ingen db_path
        self.assertEqual(self.rader[-1]["typ"], "fel")
        self.assertIn("db_path", self.rader[-1]["text"])

    def test_ej_implementerat_jobb_ger_fel_event(self):
        worker.main(["gallra", "{}"])
        self.assertEqual(self.rader[-1]["typ"], "fel")


class TestSubprocess(unittest.TestCase):
    def test_kor_demo_skarpt(self):
        """Skarp subprocess — bevisar hela röret (spawn → JSON-rader → events)."""
        sedda = []
        r = korning.kor_subprocess(["demo", '{"steg": 4}'], lyssnare=sedda.append)
        self.assertEqual(r["returkod"], 0)
        typer = [e["typ"] for e in r["events"]]
        self.assertEqual(typer[0], "start")
        self.assertIn("klar", typer)
        self.assertEqual(sum(1 for t in typer if t == "progress"), 4)
        self.assertEqual(len(sedda), len(r["events"]))     # lyssnaren fick allt


def _har_sklearn():
    try:
        import sklearn  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_har_sklearn(), "sklearn saknas")
class TestTranaJobbViaWorker(unittest.TestCase):
    """Skarp: seedar en scratch-db med facit och tränar via worker-processen
    (python -m dpt2.worker trana) — bevisar IPC + träning ur lagrade vektorer."""

    def test_trana_jobb_ger_klar_och_modellfil(self):
        import json
        import tempfile
        from pathlib import Path
        from dpt2.data import db, store

        d = Path(tempfile.mkdtemp())
        dbp = d / "scratch.db"
        conn = db.oppna(dbp)
        for u in range(2):
            fid = store.spara_facit(conn, match_namn=f"Match {u} 2-0",
                                    sport="fotboll", n=30)
            rader = []
            for i in range(30):
                hog = i % 2 == 0
                v = [0.0] * 19
                v[0] = 5.0 + (i % 3) if hog else (i % 3) * 0.1
                rader.append((f"m{u}s{i}", 1 if hog else 0, 1.0, v))
            store.ersatt_facit_rader(conn, fid, rader)
        conn.close()

        pkl = d / "modell.pkl"
        r = korning.kor_subprocess(
            ["trana", json.dumps({"db_path": str(dbp), "modell_path": str(pkl),
                                  "typ": "arkiv"})])
        self.assertEqual(r["returkod"], 0)
        typer = [e["typ"] for e in r["events"]]
        self.assertIn("klar", typer)
        self.assertTrue(pkl.exists())
        klar = next(e for e in r["events"] if e["typ"] == "klar")
        self.assertEqual(klar["resultat"]["n_uppdrag"], 2)

    def test_trana_utan_facit_ger_fel(self):
        import json
        import tempfile
        from pathlib import Path
        from dpt2.data import db

        dbp = Path(tempfile.mkdtemp()) / "tom.db"
        db.oppna(dbp).close()
        r = korning.kor_subprocess(
            ["trana", json.dumps({"db_path": str(dbp), "typ": "arkiv"})])
        self.assertEqual(r["events"][-1]["typ"], "fel")


if __name__ == "__main__":
    unittest.main()

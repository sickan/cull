"""★-utövare (M-16, Stig 24/7): favoriten bor på PERSONEN i registret (lag
kind='individ') och följer över grenar — som iOS-fältflödets utövar-stjärnor.
Vaktar: v47-migrationen (kolumnen finns i färsk OCH migrerad db), togglen,
och att gren-detaljens deltagarrader bär flaggan."""

import unittest

from dpt2.data import db
from dpt2.data import store
from dpt2.motorer import masterskap


class TestUtovareFavorit(unittest.TestCase):
    def setUp(self):
        self.conn = db.oppna(":memory:")

    def _utovare(self, namn="A. Lindqvist"):
        uid = f"u-{namn.replace(' ', '')}"
        self.conn.execute(
            "INSERT INTO lag(id, namn, kind, sport, klubb) "
            "VALUES(?, ?, 'individ', 'friidrott', 'Malmö AI')", (uid, namn))
        self.conn.commit()
        return uid

    def test_farsk_db_har_kolumnen(self):
        kol = [r[1] for r in self.conn.execute("PRAGMA table_info(lag)")]
        self.assertIn("favorit", kol)

    def test_toggle_persisterar(self):
        uid = self._utovare()
        self.assertTrue(store.satt_utovare_favorit(self.conn, uid, True))
        rad = self.conn.execute("SELECT favorit FROM lag WHERE id=?",
                                (uid,)).fetchone()
        self.assertEqual(rad[0], 1)
        store.satt_utovare_favorit(self.conn, uid, False)
        rad = self.conn.execute("SELECT favorit FROM lag WHERE id=?",
                                (uid,)).fetchone()
        self.assertEqual(rad[0], 0)

    def test_okand_utovare_ger_false(self):
        self.assertFalse(store.satt_utovare_favorit(self.conn, "finns-ej", True))

    def test_deltagarrad_bar_favoriten(self):
        self.assertTrue(masterskap.deltagarrad(
            {"id": "u1", "namn": "A", "favorit": 1})["favorit"])
        self.assertFalse(masterskap.deltagarrad(
            {"id": "u2", "namn": "B", "favorit": 0})["favorit"])
        self.assertFalse(masterskap.deltagarrad(
            {"id": "u3", "namn": "C"})["favorit"], "saknad flagga = inte favorit")

    def test_disciplin_deltagare_far_flaggan(self):
        uid = self._utovare()
        self.conn.execute(
            "INSERT INTO tavling(id, namn, typ, sport) VALUES('t1', 'SM', 'cup', 'friidrott')")
        self.conn.execute(
            "INSERT INTO disciplin(id, tavling_id, namn) "
            "VALUES('d1', 't1', 'Höjd')")
        self.conn.execute(
            "INSERT INTO disciplin_deltagare(disciplin_id, lag_id) "
            "VALUES('d1', ?)", (uid,))
        store.satt_utovare_favorit(self.conn, uid, True)
        delt = store.disciplin_deltagare(self.conn, "d1")
        self.assertEqual(len(delt), 1)
        self.assertEqual(delt[0]["favorit"], 1)

    def test_startnummer_foljer_kopplingen(self):
        # v47 (Stig 24/7): numret ur startlistan lagras på kopplingen och
        # följer till deltagarlistan + paketet (iOS visar det).
        uid = self._utovare()
        self.conn.execute(
            "INSERT INTO tavling(id, namn, typ, sport) VALUES('t1', 'SM', 'cup', 'friidrott')")
        self.conn.execute(
            "INSERT INTO disciplin(id, tavling_id, namn) VALUES('d1', 't1', 'Höjd')")
        store.koppla_disciplin_deltagare(self.conn, "d1", uid, nr="47")
        delt = store.disciplin_deltagare(self.conn, "d1")
        self.assertEqual(delt[0]["nr"], "47")
        self.assertEqual(masterskap.deltagarrad(delt[0])["nr"], "47")
        # Omkoppling utan nr skriver ALDRIG över med tomt.
        store.koppla_disciplin_deltagare(self.conn, "d1", uid)
        self.assertEqual(store.disciplin_deltagare(self.conn, "d1")[0]["nr"], "47")

    def test_migration_fran_v46(self):
        # En db utan kolumnen (simulerad äldre) → migrationssteget lägger den.
        gammal = db.oppna(":memory:")
        gammal.execute("ALTER TABLE lag RENAME COLUMN favorit TO favorit_bort")
        # _migrera-steget är idempotent och guardat på _har_kolumn:
        from dpt2.data.db import _har_kolumn
        self.assertFalse(_har_kolumn(gammal, "lag", "favorit"))
        gammal.execute("ALTER TABLE lag ADD COLUMN favorit "
                       "INTEGER NOT NULL DEFAULT 0")
        self.assertTrue(_har_kolumn(gammal, "lag", "favorit"))


if __name__ == "__main__":
    unittest.main()

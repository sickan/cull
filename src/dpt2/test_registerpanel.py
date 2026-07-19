"""C12/M-1: vakter för det delade registret (Lag & Utövare) i UI-källan.

Panelen är ren presentation — det finns ingen körbar Svelte-runtime i sviten.
Det som ändå MÅSTE gå att regressionsskydda är designens låsta invarianter och
de fält som lyftes ut ur utövaren. Testerna läser därför källfilerna och
kontrollerar strukturen; de fångar exakt det som gick sönder förr (klassen som
textetikett, lag-fält som läcker in på personen).
"""

import re
import unittest
from pathlib import Path

UI = Path(__file__).parent / "ui" / "src"
LAG = (UI / "panels" / "Lag.svelte").read_text(encoding="utf-8")
GREN = (UI / "lib" / "gren.js").read_text(encoding="utf-8")
BRICKA = (UI / "lib" / "Lagbricka.svelte").read_text(encoding="utf-8")


def _registerlistan(kalla):
    """Registerlistans markup — utan den döda Tävlingar-vyn som ligger kvar
    oåtkomlig i filen (D11b §1) och väntar på en egen städ-pass."""
    return kalla[:kalla.index("{#each tavlingar as t (t.id)}")]


def _utovargrenen(kalla):
    """Utövar-grenen i den DELADE EDITORN: {#if l.kind === 'individ'} … {:else}.

    Ankras på klass-kommentaren så vi inte råkar fånga radens avatar-if (som
    också växlar på slaget). Klipps ut så vi kan påstå saker om VAD SOM INTE
    finns där — lag-fälten som tidigare läckte in på personen.
    """
    ankare = kalla.index("<!-- Klassen är PERSONENS egen")
    start = kalla.rindex("{#if l.kind === 'individ'}", 0, ankare)
    return kalla[start:kalla.index("{:else}", ankare)]


class TestKlasspalett(unittest.TestCase):
    """Låst invariant: Dam #8E5A86 · Herr #3E7C87 · Mixed #6E8757."""

    def test_palett_ar_last(self):
        for klass, hexv in (("herr", "#3E7C87"), ("dam", "#8E5A86"),
                            ("mixed", "#6E8757")):
            self.assertIn(f"{klass}: '{hexv}'", GREN)

    def test_okand_klass_ger_ingen_kant(self):
        # Utövar-avataren och porträttet får kant BARA när klassen är satt.
        for rad in re.findall(r"kant=\{[^}]*\}", LAG):
            self.assertIn("l.gren ?", rad, rad)
            self.assertIn("''", rad, rad)
        self.assertIn("kant ? `border-left:3px solid ${kant};` : ''", BRICKA)

    def test_klassen_visas_aldrig_som_textetikett(self):
        # Den färgade klass-etiketten i listraden (.grenlbl2) är borta; kvar är
        # färgstapeln i klassknappen och avatarens kant.
        self.assertNotIn("grenlbl2", _registerlistan(LAG))
        self.assertIn("klasstapel", LAG)
        # metaRad får inte skriva ut klassen i klartext.
        meta = LAG[LAG.index("function metaRad"):LAG.index("function tavlingNamn")]
        self.assertNotIn("GREN_ETIKETT", meta)


class TestDeladEditor(unittest.TestCase):
    """M-1: ett register, ett Slag-val, rätt fält per slag."""

    def test_slagvalet_byter_formular(self):
        self.assertIn("const SLAG = [['alla', 'Alla'], ['individ', 'Utövare'], "
                      "['team', 'Lag']]", LAG)
        self.assertIn("sattKind(l, 'individ')", LAG)
        self.assertIn("sattKind(l, 'team')", LAG)

    def test_utovarformularets_falt(self):
        # Porträtt, namn och klubb är det DELADE huvudet (rätt etikett per
        # slag); klass, @-konto och anteckning är utövarens egna.
        self.assertIn("Byt porträtt…", LAG)
        self.assertIn("placeholder={l.kind === 'individ' ? 'Namn' : 'Lagnamn'}",
                      LAG)
        self.assertIn("placeholder={l.kind === 'individ' ? 'Klubb' "
                      ": 'Förening / förbund'}", LAG)
        u = _utovargrenen(LAG)
        for markor in ("Klass",                   # personens egen klass
                       "— personens egen",
                       "@-konto (Instagram)",     # @-konto med @-prefix
                       "atprefix",
                       "l.anteckning"):           # anteckning
            self.assertIn(markor, u, markor)

    def test_lagfalten_lacker_inte_in_pa_utovaren(self):
        u = _utovargrenen(LAG)
        for lackage in ("profilfarg",        # profilfärg
                        "stall_hemma",       # ställfärger
                        "stall_borta",
                        "arkiverad",         # arkivera + matchspråket
                        "kopplbox"):         # flat tävling-chip
            self.assertNotIn(lackage, u, lackage)

    def test_lagformularet_bar_lagbehoven(self):
        # Allt som lyftes ut ur utövaren ska finnas kvar — på laget.
        for markor in ("stall_hemma", "stall_borta", "Byt lagemblem…",
                       "Läs in spelare…", "Arkivera lag — göms i registret.",
                       "Matcher som redan använder laget påverkas inte."):
            self.assertIn(markor, LAG, markor)

    def test_plats_lamnad_for_m2(self):
        # "Tävlar i" byggs i M-2 (härlett ur disciplin_deltagare) — platsen ska
        # finnas, men ingen flat tävling-chip på personen.
        self.assertIn("Tävlar i", LAG)
        self.assertIn("tavlarplats", LAG)


class TestRegisterlistan(unittest.TestCase):
    def test_filterchips_ar_slag(self):
        self.assertIn("lagSlagCounts", LAG)
        self.assertNotIn("lagGren", LAG)          # gren-filtret är ersatt

    def test_soket_traffar_namn_och_klubb(self):
        self.assertIn("norm(`${l.namn} ${l.klubb || ''}`).includes(norm(sok))",
                      LAG)

    def test_avatarerna_skiljer_slagen(self):
        # Lag = rundad kvadrat med diagonal 50/50-gradient i ställfärgerna.
        self.assertIn('form="kvadrat"', LAG)
        self.assertIn("farg2={l.stall_borta || ''}", LAG)
        self.assertIn("linear-gradient(135deg, ${farg} 50%, ${farg2} 50%)",
                      BRICKA)


if __name__ == "__main__":
    unittest.main()

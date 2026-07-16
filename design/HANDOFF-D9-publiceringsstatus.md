# Design-handoff D9 — Publiceringsstatus-språket (NYTT design-jobb)

*2026-07-16 · Till: Claude Design · Från: Code · Hör till nästa stora
code-tema (Publiceringskedjan v2) — designen behövs INNAN FEAT-12 byggs,
så det här är rätt tid att ta den.*

## Bakgrund

Stig har specat statusmodellen (FEAT-12): 🔵 **Utkast** · 🟡 **Publicerad**
· 🟢 **Live** · 🔴 **Fel** — och att den gamla "Utkast"-knappen fasas ut när
automatiken finns. Code bygger samtidigt FEAT-09 (auto-status: appen pollar
tills allt är live — bort med manuella "Kolla status") och FEAT-13
(purge/spegling som löser dubbletterna). **Vad som ska hända är bestämt —
D9 är HUR det ser ut och var.**

## Dagens läge (fakta)

- Innehålls-biblioteket (DPT2) visar poster med en grön markering till höger
  + separat "Utkast"-knapp; katalogen "Publicerat" har dubbletter (fixas av
  FEAT-13) och ingen skillnad på "skickad" vs "faktiskt live på webben".
- Statuskedjan tekniskt: utkast (lokalt) → publicerad (pushad till workern)
  → live (byggd + deployad på sajten, verifierbar via poll) → fel (någon
  del föll).

## Frågor att landa

1. **Statusfärgens form i biblioteket:** prick? kant? chip med text? Var på
   kortet/raden — och hur skiljer sig list- vs kortvy?
2. **Fel-tillståndet:** 🔴 behöver mer än färg — var visas felorsaken och
   "försök igen"? (Matchpubliceringen har redan ett per-kanal-utfall +
   "Försök igen"-mönster att återanvända.)
3. **Övergångarna:** publicerad→live sker asynkront (bygge ~1–2 min). Visas
   en mellananimation/puls? Vad ser man UNDER pågående poll?
4. **Utkastknappens utfasning:** vad ersätter den — sparas allt löpande som
   utkast tills man trycker Publicera (dagens autospar-tanke)?
5. **Konsekvens över ytor:** samma språk i Innehåll, Matchpublicering och
   ev. På gång — en gemensam komponent?

## Leverabel

Mockup av Innehålls-biblioteket med de fyra statusarna + fel-detaljen +
övergångsbeteendet i text. Referens: `BACKLOG.md` (FEAT-08/09/12/13,
BUG-06/07/08 — hela Publiceringskedjan v2-paketet).

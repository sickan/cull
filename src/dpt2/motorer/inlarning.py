"""Träningskärna (KÄRNA) — tränar din-smak/arkiv-modellen ur (features, etikett)
och poängsätter nya bilder. Migrerad ur gamla dpt.inlarning, frikopplad från
facit-fillayouten: `trana` tar färdiga uppdrag (X, y, sport) och returnerar
modell-paketet i EXAKT samma format som gamla `modell.pkl` (modell-växlaren +
poangsatt_med_modell förstår det).

INVARIANT (beslut 3): z-norm sker PER UPPDRAG i BÅDE träning och inferens —
annars driftar poängen. `_znorm` + paketformatet är migrerade verbatim.

Recompute+retrain-flödet (omräkna facit-features med nuvarande libs, behåll de
bevarade y-etiketterna, träna om) bygger sina `uppdrag` ur
extraktion.features_for_bilder + facit_rad och anropar `trana` här.
"""

import pickle
from datetime import datetime

import numpy as np

# L1-straff (liblinear) korsvaliderar C och nollställer brusiga features →
# automatisk feature-gallring. Faller tillbaka på L2 när data är tunt.
_Cs = [0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0]


def _znorm(X):
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd[sd < 1e-6] = 1.0
    return (X - mu) / sd


def _ny_modell(n_folds, n_pos):
    from sklearn.linear_model import LogisticRegression, LogisticRegressionCV
    if n_folds >= 3 and n_pos >= n_folds:
        return LogisticRegressionCV(
            Cs=_Cs, cv=n_folds, scoring="roc_auc", penalty="l1",
            solver="liblinear", class_weight="balanced", max_iter=2000)
    return LogisticRegression(class_weight="balanced", max_iter=2000, C=1.0)


def _trana_en(X, y, n_uppdrag, features, etikett="", logg=print):
    """Tränar en LogisticRegression(CV) på (redan per-uppdrag-z-normad) X, y.
    Returnerar (modell, auc|None). X = vstack av z-normade uppdrag."""
    from sklearn.model_selection import cross_val_score
    n_folds = min(5, max(2, n_uppdrag))
    n_pos = int(np.sum(y))
    auc = None
    try:
        cv = cross_val_score(_ny_modell(n_folds, n_pos), X, y, cv=n_folds,
                             scoring="roc_auc")
        auc = float(cv.mean())
        logg(f"  AUC: {auc:.3f} ± {cv.std():.3f}")
    except Exception as e:
        logg(f"  (korsvalidering hoppades: {e})")
    lr = _ny_modell(n_folds, n_pos)
    lr.fit(X, y)
    coef = lr.coef_[0]
    for fn, w in sorted(zip(features, coef), key=lambda t: -abs(t[1]))[:6]:
        logg(f"    {fn:<12}{w:+.2f}")
    return lr, auc


def trana(uppdrag, *, features, typ="din_smak", logg=print):
    """uppdrag = [(X_raw, y, sport)] per uppdrag (X_raw = lista/array RÅ-features
    i `features`-ordning). Z-normar per uppdrag, tränar kombinerad modell +
    sportmodeller (≥5 uppdrag/sport). Returnerar modell-paketet (dict)."""
    X_list, y_list, sport_list = [], [], []
    for X_raw, y, sport in uppdrag:
        X_raw = np.asarray(X_raw, float)
        y = np.asarray(y)
        if len(X_raw) == 0 or y.sum() == 0:
            continue
        X_list.append(_znorm(X_raw))
        y_list.append(y)
        sport_list.append(sport or "okänd")
    if not X_list:
        raise ValueError("Inga användbara uppdrag (tomma eller utan positiva).")

    X_all = np.vstack(X_list)
    y_all = np.concatenate(y_list)
    n_valda = int(y_all.sum())
    logg(f"Träningsdata: {len(y_all)} bilder, {n_valda} valda "
         f"({n_valda / len(y_all) * 100:.1f}%) från {len(X_list)} uppdrag.")

    logg("=== Kombinerad modell ===")
    modell, _ = _trana_en(X_all, y_all, len(X_list), features, logg=logg)

    sport_modeller = {}
    for sport in sorted(s for s in set(sport_list) if s != "okänd"):
        idx = [i for i, s in enumerate(sport_list) if s == sport]
        if len(idx) < 5:
            continue
        Xs = np.vstack([X_list[i] for i in idx])
        ys = np.concatenate([y_list[i] for i in idx])
        logg(f"=== {sport.capitalize()} ({len(idx)} uppdrag) ===")
        sport_modeller[sport], _ = _trana_en(Xs, ys, len(idx), features,
                                             etikett=sport, logg=logg)

    sport_stats = {s: {"n_uppdrag": sport_list.count(s)}
                   for s in set(sport_list) if s != "okänd"}
    return {
        "modell": modell, "sport_modeller": sport_modeller,
        "features": list(features), "n_uppdrag": len(X_list),
        "n_valda": n_valda, "sport_stats": sport_stats, "rank_modell": None,
        "modell_typ": typ,
        "sparad": datetime.now().isoformat(timespec="seconds"),
    }


def spara_modell(paket, path):
    import os
    os.makedirs(os.path.dirname(str(path)) or ".", exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(paket, f)
    return path


def ladda_modell(path):
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def poangsatt_med_modell(resultat, paket, sport=None):
    """Skriver r['poang'] (+ r['modell_p']) för alla i resultat, z-normaliserat
    per uppdrag. Sportspecifik modell om tillgänglig, annars kombinerad.
    resultat = lista dicts med feature-värden (FEATURES-nycklar). Migrerad verbatim."""
    feats = paket["features"]
    lr = paket.get("sport_modeller", {}).get(sport) if sport else None
    if lr is None:
        lr = paket["modell"]
    X = np.array([[float(r.get(k, 0.0)) for k in feats] for r in resultat])
    if len(X) == 0:
        return
    Xn = _znorm(X)
    proba = lr.predict_proba(Xn)[:, 1]
    for r, p in zip(resultat, proba):
        r["poang"] = float(p)
        r["modell_p"] = float(p)

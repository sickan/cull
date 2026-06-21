"""
CLIP-lager: zero-shot semantiska features för sportbilder.

Använder OpenAI-CLIP (redan installerat i venv:en) för att poängsätta varje
bild mot ett fåtal textbegrepp som är redaktionellt relevanta vid culling:
firande, närkamp, porträtt, uppvärmning (västar!) och publik/passivt.

Inga vikter behöver tränas — CLIP är förtränat. Cosinuslikheten mot varje
begrepp blir en feature som den personliga modellen kan vikta själv.
Prompterna mallas med sportens engelska namn när sporten är känd.
"""

import cv2
import numpy as np

# Feature-namn som exponeras (måste matcha CLIP_FEATURES nedan).
CLIP_FEATURES = ["clip_firande", "clip_narkamp", "clip_portratt",
                 "clip_uppvarmning", "clip_publik"]

# Engelskt sportord för promptmallar.
_SPORT_ORD = {
    "fotboll": "soccer", "handboll": "handball",
    "volleyboll": "volleyball", "innebandy": "floorball",
}

# Begreppsgrupper → paraphraser. Bild-poäng per grupp = max cosinuslikhet
# över gruppens prompter.
_PROMPT_GRUPPER = {
    "clip_firande": [
        "a {s} player celebrating a goal with arms raised",
        "athletes celebrating together after scoring",
        "a jubilant sports celebration, fists in the air",
    ],
    "clip_narkamp": [
        "two {s} players battling for the ball",
        "an intense duel between players during a match",
        "a hard tackle in a {s} game",
    ],
    "clip_portratt": [
        "a sharp close-up of a single {s} player's face",
        "a portrait of an athlete showing emotion",
        "one player in focus with a blurred background",
    ],
    "clip_uppvarmning": [
        "players warming up wearing training bibs and vests",
        "{s} players in warm-up vests before the match",
        "athletes jogging during a pre-match warm-up",
    ],
    "clip_publik": [
        "spectators and crowd in the stands",
        "substitutes sitting on the bench, no action",
        "a static photo with no players in action",
    ],
}


def ladda_clip(device="cpu", modell="ViT-B/32"):
    """Laddar CLIP. Returnerar dict med model/preprocess eller None vid fel."""
    try:
        import clip
        import torch
        with __import__("warnings").catch_warnings():
            __import__("warnings").simplefilter("ignore")
            model, preprocess = clip.load(modell, device=device)
        model.eval()
        print(f"CLIP ({modell}): aktivt ({device.upper()})")
        return {"model": model, "preprocess": preprocess, "device": device}
    except Exception as e:
        print(f"CLIP: ej tillgängligt ({e})")
        return None


def bygg_text_features(clip_pak, sport=None):
    """Förberäknar normaliserade text-embeddings per begreppsgrupp för en sport.
    Returnerar dict grupp -> tensor [n_prompter, dim]."""
    import clip
    import torch
    s = _SPORT_ORD.get(sport, "sports")
    model, device = clip_pak["model"], clip_pak["device"]
    ut = {}
    with torch.no_grad():
        for grupp, prompter in _PROMPT_GRUPPER.items():
            text = clip.tokenize([p.format(s=s) for p in prompter]).to(device)
            tf = model.encode_text(text).float()
            tf = tf / tf.norm(dim=-1, keepdim=True)
            ut[grupp] = tf
    return ut


def clip_features_batch(imgs_bgr, clip_pak, text_pak):
    """Returnerar en lista med dict (CLIP_FEATURES → cosinuslikhet) per bild."""
    import torch
    from PIL import Image
    model = clip_pak["model"]
    preprocess = clip_pak["preprocess"]
    device = clip_pak["device"]

    tensors = []
    for img in imgs_bgr:
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        tensors.append(preprocess(Image.fromarray(rgb)))
    batch = torch.stack(tensors).to(device)

    with torch.no_grad():
        feat = model.encode_image(batch).float()
        feat = feat / feat.norm(dim=-1, keepdim=True)        # [N, dim]
        rader = [{} for _ in range(len(imgs_bgr))]
        for grupp in CLIP_FEATURES:
            sim = feat @ text_pak[grupp].t()                  # [N, n_prompter]
            bästa = sim.max(dim=1).values.cpu().tolist()      # max över prompter
            for i, v in enumerate(bästa):
                rader[i][grupp] = float(v)
    return rader

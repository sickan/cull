"""Generera XMP-sidecars med upprätning (rätning av lutande horisont)."""

import re
import cv2
import numpy as np
from pathlib import Path

# Preset-metadata som inte hör hemma i en bild-sidecar (bara presethantering).
_PRESET_DROPPA_ATTR = {
    "PresetType", "Cluster", "UUID", "SupportsAmount2", "SupportsAmount",
    "SupportsColor", "SupportsMonochrome", "SupportsHighDynamicRange",
    "SupportsNormalDynamicRange", "SupportsSceneReferred",
    "SupportsOutputReferred", "RequiresRGBTables", "ShowInPresets",
    "ShowInQuickActions", "CameraModelRestriction", "Copyright",
    "ContactInfo", "HasSettings",
}
_PRESET_DROPPA_ELEM = {"Name", "ShortName", "SortName", "Group", "Description"}


def las_preset(path):
    """Läser ett Camera Raw/Lightroom-preset (.xmp) och returnerar
    {'attrs': {namn: värde}, 'inner': 'nästlad xml'} — develop-inställningar,
    tonkurva och Look. Preset-metadata (namn, UUID, Supports…) filtreras bort.
    Returnerar None om filen inte kan läsas/tolkas."""
    try:
        txt = Path(path).read_text(encoding="utf-8")
    except Exception:
        return None
    # Yttre rdf:Description i två former: med kropp (Adobe-presets, tonkurva/
    # Look — greedy till SISTA stängningen så vi inte stannar i Look-blocket)
    # ELLER självstängande (appens egna + enkla PM/Adobe-sidecars: attr + />).
    m = re.search(r"<rdf:Description\b([^>]*)>(.*)</rdf:Description>", txt, re.S)
    if m:
        attr_blob, inner = m.group(1), m.group(2)
    else:
        m = re.search(r"<rdf:Description\b([^>]*?)/>", txt, re.S)
        if not m:
            return None
        attr_blob, inner = m.group(1), ""
    attrs = {}
    # Stöd både dubbla (Adobe/PM-presets) och enkla citattecken (appens egna
    # sidecars) → merge bevarar develop-inställningar oavsett källa.
    for namn, val in re.findall(r"crs:(\w+)\s*=\s*['\"]([^'\"]*)['\"]", attr_blob):
        if namn not in _PRESET_DROPPA_ATTR:
            attrs[namn] = val
    for elem in _PRESET_DROPPA_ELEM:
        inner = re.sub(rf"<crs:{elem}\b.*?</crs:{elem}>", "", inner, flags=re.S)
    if not attrs:
        return None
    return {"attrs": attrs, "inner": inner.strip()}

XMP_MALL = """\
<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>
<x:xmpmeta xmlns:x='adobe:ns:meta/' x:xmptk='cull'>
  <rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>
    <rdf:Description rdf:about=''
      xmlns:crs='http://ns.adobe.com/camera-raw-settings/1.0/'
      xmlns:xmp='http://ns.adobe.com/xap/1.0/'{rating_attr}{label_attr}
      crs:Version='15.0'
      crs:ProcessVersion='11.0'
      crs:HasCrop='{has_crop}'
      crs:CropTop='{top:.6f}'
      crs:CropLeft='{left:.6f}'
      crs:CropBottom='{bottom:.6f}'
      crs:CropRight='{right:.6f}'
      crs:CropAngle='{crop_angle:.2f}'
      crs:CropConstrainToWarp='{constrain}'
      crs:StraightenAngle='0.00'{extra}
    />
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end='w'?>"""


def berakna_uppratning(img_bgr):
    """
    Detekterar horisontella linjer (planets kant/mittlinje) med Hough-transform
    och returnerar korrektionsvinkeln i grader.
    """
    h, w = img_bgr.shape[:2]
    roi = img_bgr[h // 2:, :]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180,
                             threshold=80, minLineLength=w // 5, maxLineGap=20)
    if lines is None:
        return 0.0
    vinklar = []
    for x1, y1, x2, y2 in lines[:, 0]:
        dx, dy = x2 - x1, y2 - y1
        if abs(dx) < 10:
            continue
        v = np.degrees(np.arctan2(dy, dx))
        if abs(v) < 15:
            vinklar.append(v)
    if not vinklar:
        return 0.0
    return float(np.clip(-float(np.median(vinklar)), -5.0, 5.0))


def brus_av_iso(iso):
    """Mappar ISO till (luminans-NR, färg-NR, luminans-detalj) för crs.

    Konservativt – sportredaktörer vill ha kvar lite korn. Returnerar None
    under ~1600 (kamerans/LR:s standard räcker)."""
    if not iso or iso < 1600:
        return None
    if iso < 3200:
        return (10, 25, 50)
    if iso < 6400:
        return (18, 30, 50)
    if iso < 12800:
        return (28, 40, 50)
    return (38, 55, 40)


PRESET_MALL = """\
<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>
<x:xmpmeta xmlns:x='adobe:ns:meta/' x:xmptk='cull'>
  <rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>
    <rdf:Description rdf:about=''
      xmlns:crs='http://ns.adobe.com/camera-raw-settings/1.0/'
      xmlns:xmp='http://ns.adobe.com/xap/1.0/'{rating_attr}{label_attr}
{attr}>{inner}
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end='w'?>"""


def _bygg_med_preset(preset, over, has_crop, top, left, bottom, right,
                     crop_angle, constrain, rating_attr="", label_attr=""):
    """Presetets develop-look som bas, med våra per-bild-värden som override."""
    attrs = dict(preset["attrs"])
    attrs["HasCrop"] = has_crop
    attrs["CropTop"] = f"{top:.6f}"
    attrs["CropLeft"] = f"{left:.6f}"
    attrs["CropBottom"] = f"{bottom:.6f}"
    attrs["CropRight"] = f"{right:.6f}"
    attrs["CropAngle"] = f"{crop_angle:.2f}"
    attrs["CropConstrainToWarp"] = constrain
    attrs["StraightenAngle"] = "0.00"
    attrs.setdefault("Version", "15.0")
    attrs.setdefault("ProcessVersion", "11.0")
    attrs.update(over)   # våra värden vinner över presetets
    rader = "\n".join(f"      crs:{k}='{v}'" for k, v in attrs.items())
    inner = ("\n" + preset["inner"]) if preset.get("inner") else ""
    return PRESET_MALL.format(attr=rader, inner=inner,
                              rating_attr=rating_attr, label_attr=label_attr)


def skriv_xmp(nef_path, crop=None, vinkel=0.0,
              exposure=None, temperatur=None, tint=None, profil=None,
              iso=None, objektiv=False, preset=None, exp_bump=0.0, rating=None,
              label=None):
    """Skriver en XMP-sidecar bredvid NEF-filen.

    exposure:    relativ EV-justering (crs:Exposure2012), eller None.
    temperatur:  absolut Kelvin (crs:Temperature, WhiteBalance=Custom), eller None.
    tint:        absolut tint (crs:Tint), används med temperatur.
    profil:      kameraprofil (crs:CameraProfile), t.ex. 'Camera Neutral'.
    iso:         EXIF-ISO → ISO-baserad brusreducering, eller None.
    objektiv:    True → aktivera objektivprofil-korrigering (crs:LensProfileEnable).
    preset:      parsat husstil-preset (las_preset) som bakas in, eller None.
    exp_bump:    generell EV-knuff ovanpå exposure.
    """
    exp_final = (exposure or 0.0) + (exp_bump or 0.0)
    skriv_exp = exposure is not None or abs(exp_bump or 0.0) > 0.005

    # Upprätning i Lightroom = crs:CropAngle med HasCrop=True (StraightenAngle
    # ignoreras utan aktiv beskärning). ConstrainToWarp=1 → LR beskär in kilen.
    rakta = vinkel is not None and abs(vinkel) > 0.005
    if crop:
        top, left, bottom, right = crop
        has_crop = "True"
    else:
        top, left, bottom, right = 0.0, 0.0, 1.0, 1.0
        has_crop = "True" if rakta else "False"
    crop_angle = vinkel if rakta else 0.0
    constrain = "1" if rakta else "0"
    rating_attr = (f"\n      xmp:Rating='{int(rating)}'"
                   if rating else "")
    # Färgetikett (xmp:Label) — t.ex. 'Blue' för kamera-skyddade bilder.
    # Lightroom läser etiketten och visar/filtrerar på färg.
    label_attr = (f"\n      xmp:Label='{label}'" if label else "")

    # Per-bild-värden (ordning bevaras → samma utdata som tidigare).
    over = {}
    if profil:
        over["CameraProfile"] = profil
    if skriv_exp:
        over["Exposure2012"] = f"{exp_final:+.2f}"
    if temperatur is not None:
        over["WhiteBalance"] = "Custom"
        over["Temperature"] = str(int(round(temperatur)))
        over["Tint"] = str(int(round(tint or 0)))
    nr = brus_av_iso(iso)
    if nr:
        lum, farg, detalj = nr
        over["LuminanceSmoothing"] = str(lum)
        over["LuminanceNoiseReductionDetail"] = str(detalj)
        over["ColorNoiseReduction"] = str(farg)
    if objektiv:
        over["LensProfileEnable"] = "1"
        over["LensProfileSetup"] = "LensDefaults"

    if preset:
        innehall = _bygg_med_preset(preset, over, has_crop,
                                    top, left, bottom, right,
                                    crop_angle, constrain, rating_attr,
                                    label_attr)
    else:
        rader = [f"crs:{k}='{v}'" for k, v in over.items()]
        extra = ("\n      " + "\n      ".join(rader)) if rader else ""
        innehall = XMP_MALL.format(
            has_crop=has_crop,
            top=top, left=left, bottom=bottom, right=right,
            crop_angle=crop_angle, constrain=constrain, extra=extra,
            rating_attr=rating_attr, label_attr=label_attr,
        )
    xmp_path = Path(nef_path).with_suffix(".xmp")
    xmp_path.write_text(innehall, encoding="utf-8")
    return xmp_path

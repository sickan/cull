"""Apple Vision (lokalt, Neural Engine): horisont-detektering för upprätning.

VNDetectHorizonRequest skattar kamerans rollvinkel ur scenen — pålitligare än
Hough-linjer som bara hittar planlinjer. Funkar bäst utomhus/med tydlig
horisont; returnerar None när Vision inte hittar någon (då faller anroparen
tillbaka på Hough).
"""

import math


def tillganglig():
    try:
        import Vision, Quartz  # noqa: F401
        return True
    except Exception:
        return False


def _cgimage(path):
    import Quartz
    from Foundation import NSURL
    url = NSURL.fileURLWithPath_(str(path))
    src = Quartz.CGImageSourceCreateWithURL(url, None)
    if not src:
        return None
    return Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)


def _cgimage_av_bytes(data):
    import Quartz
    from Foundation import NSData
    nsd = NSData.dataWithBytes_length_(data, len(data))
    src = Quartz.CGImageSourceCreateWithData(nsd, None)
    if not src:
        return None
    return Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)


def _estetik_av_cg(cg):
    try:
        import Vision
    except Exception:
        return None
    if cg is None:
        return None
    try:
        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
            cg, None)
        req = Vision.VNCalculateImageAestheticsScoresRequest.alloc().init()
        if not handler.performRequests_error_([req], None):
            return None
        res = req.results()
        if not res:
            return None
        o = res[0]
        return float(o.overallScore()), bool(o.isUtility())
    except Exception:
        return None


def estetik_poang(path):
    """Apple Vision estetikpoäng ur en fil: overallScore i [-1, 1] (högre =
    snyggare) + is_utility. Returnerar (score, is_utility) eller None."""
    return _estetik_av_cg(_cgimage(path))


def estetik_poang_bgr(img_bgr):
    """Som estetik_poang men ur en cv2-BGR-bild (in-minnes, ingen temp-fil) —
    för träningens batchade bilder."""
    import cv2
    ok, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        return None
    return _estetik_av_cg(_cgimage_av_bytes(buf.tobytes()))


def horisont_vinkel(path, max_grader=8.0):
    """Returnerar upprätningsvinkel i grader (crs:StraightenAngle-konvention),
    eller None om Vision inte hittar en horisont."""
    try:
        import Vision
    except Exception:
        return None
    cg = _cgimage(path)
    if cg is None:
        return None
    try:
        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
            cg, None)
        req = Vision.VNDetectHorizonRequest.alloc().init()
        if not handler.performRequests_error_([req], None):
            return None
        res = req.results()
        if not res:
            return None
        # VNHorizonObservation.angle() = horisontens lutning i radianer.
        # Negativ för att rätta upp (samma konvention som Hough-vägen).
        deg = -math.degrees(res[0].angle())
        if abs(deg) > max_grader:
            return None   # orimligt → lita inte på den
        return float(deg)
    except Exception:
        return None

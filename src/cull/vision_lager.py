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

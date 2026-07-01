"""Tröjfärgs-tabell (DATA) — HSV-intervall (OpenCV-skala, H 0–180) per färgnamn.

EN sanning för färgmatchning: används idag av nummer-kärnan (hemma/borta-
bestämning vid nummerkrock) och, när `ai_lager` migreras, av dess väst-/
tröjfärgsheuristik. Bröts ut ur gamla `dpt.ai_lager.FARG_HSV` vid Fas 3 så de
inte driftar isär. Lågt/högt-par = cv2.inRange-gränser för cv2.COLOR_BGR2HSV.
"""

FARG_HSV = {
    "röd":     ([0,   100, 100], [10,  255, 255]),
    "mörkröd": ([170, 100, 100], [180, 255, 255]),
    "blå":     ([100, 100,  80], [130, 255, 255]),
    "ljusblå": ([85,   80,  80], [105, 255, 255]),
    "gul":     ([20,  100, 100], [35,  255, 255]),
    "grön":    ([40,   80,  80], [80,  255, 255]),
    "vit":     ([0,     0, 180], [180,  30, 255]),
    "svart":   ([0,     0,   0], [180, 255,  60]),
    "orange":  ([10,  150, 150], [20,  255, 255]),
    "lila":    ([130,  80,  80], [160, 255, 255]),
}

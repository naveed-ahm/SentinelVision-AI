"""Generate synthetic demo traffic videos with drawn number plates.

These create clearly-artificial clips (moving colored rectangles styled as
vehicles with legible plate text) for exercising the full pipeline —
ingestion, detection is expected to be run with real YOLO weights on real
footage; these clips are for wiring/end-to-end testing without any external
credentials or footage.

Each demo camera gets its own scene (road layout, palette, vehicle mix) so
the multi-camera grid visibly shows different feeds.

Run:  python make_demo_video.py                 # highway scene only (as before)
      python make_demo_video.py --all [seconds] # all six demo-camera scenes
"""
import os
import sys

import cv2
import numpy as np

W, H, FPS = 1280, 720, 25

# Plates reused from the seed history / demo watchlist so clips, vehicles and
# watchlist entries stay coherent (GJ01AB1234 + GJ05CD5678 are on the demo watchlist).
P = {
    "AB": "GJ01AB1234", "CD": "GJ05CD5678", "EF": "GJ18EF9012", "GH": "GJ27GH3456",
    "KL": "MH12KL7890", "MN": "GJ03MN2345", "PQ": "GJ22PQ6789", "DL": "DL8CAF4567",
}

# scene key -> (filename, renderer)
SCENES = {}


def scene(filename):
    def deco(fn):
        SCENES[fn.__name__] = (filename, fn)
        return fn
    return deco


def _vehicle(frame, v):
    """Draw one vehicle rectangle-set + plate; returns nothing."""
    x, y, w, h = int(v["x"]), int(v["y"]), v["w"], v["h"]
    cv2.rectangle(frame, (x, y), (x + w, y + h), v["color"], -1)
    cv2.rectangle(frame, (x + int(w * 0.15), y - int(h * 0.35)), (x + int(w * 0.8), y), v["color"], -1)
    cv2.rectangle(frame, (x + int(w * 0.2), y - int(h * 0.28)), (x + int(w * 0.75), y - int(h * 0.05)), (180, 200, 220), -1)
    for wx in (x + int(w * 0.12), x + int(w * 0.75)):
        cv2.circle(frame, (wx, y + h), int(h * 0.16), (15, 15, 15), -1)
    pw, ph = int(w * 0.42), int(h * 0.2)
    px, py = x + int(w * 0.29), y + h - int(h * 0.32)
    cv2.rectangle(frame, (px, py), (px + pw, py + ph), (240, 240, 240), -1)
    cv2.putText(frame, v["plate"], (px + 3, py + int(ph * 0.75)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (10, 10, 10), 2)


def _render(out, seconds, background, vehicles, label):
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(out, fourcc, FPS, (W, H))
    total = FPS * seconds
    for i in range(total):
        frame = background(i)
        cv2.putText(frame, "SYNTHETIC DEMO FOOTAGE", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
        cv2.putText(frame, label, (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 60), 2)
        for v in vehicles:
            v["x"] += v["speed"]
            if v["x"] > W + 300:
                v["x"] = -v["w"] - 50
            if v["x"] < -v["w"] - 300:
                v["x"] = W + 50
            _vehicle(frame, v)
        vw.write(frame)
    vw.release()
    print(f"Wrote {out} ({seconds}s, {FPS}fps, {W}x{H})")


# ---------------- scene: SG Highway — Trial Overpass (default, as v1) ----------------

@scene("../data/demo_videos/demo_traffic.mp4")
def highway():
    def background(t):
        frame = np.full((H, W, 3), 40, dtype=np.uint8)
        frame[:120] = (30, 45, 30)
        frame[560:] = (30, 45, 30)
        cv2.rectangle(frame, (0, 120), (W, 560), (60, 60, 60), -1)
        for x in range(0, W, 90):
            cv2.rectangle(frame, (x, 335), (x + 45, 345), (200, 200, 200), -1)
        cv2.rectangle(frame, (0, 120), (W, 128), (180, 180, 180), -1)
        cv2.rectangle(frame, (0, 552), (W, 560), (180, 180, 180), -1)
        return frame

    vehicles = [
        dict(x=-220, y=200, w=200, h=110, speed=3.1, color=(90, 90, 200), plate=P["AB"]),
        dict(x=W + 160, y=430, w=230, h=125, speed=-2.6, color=(70, 140, 70), plate=P["CD"]),
        dict(x=-420, y=210, w=210, h=115, speed=2.4, color=(160, 120, 40), plate=P["EF"]),
        dict(x=W + 520, y=440, w=250, h=130, speed=-3.4, color=(50, 60, 160), plate=P["GH"]),
        dict(x=-90, y=470, w=95, h=55, speed=3.8, color=(120, 120, 130), plate=P["PQ"]),
    ]
    return background, vehicles, "SG HIGHWAY — TRIAL OVERPASS"


# ---------------- scene: CG Road — Ellis Bridge End (city street, signal) ----------------

@scene("../data/demo_videos/demo_city.mp4")
def city():
    def background(t):
        frame = np.full((H, W, 3), 70, dtype=np.uint8)
        frame[:100] = (80, 80, 90)          # buildings band
        for bx in range(0, W, 160):          # building blocks
            cv2.rectangle(frame, (bx + 10, 20), (bx + 140, 100), (60, 60, 75), -1)
        frame[600:] = (45, 45, 50)           # footpath
        cv2.rectangle(frame, (0, 100), (W, 600), (55, 55, 58), -1)
        for x in range(0, W, 70):            # lane dashes
            cv2.rectangle(frame, (x, 345), (x + 36, 353), (210, 210, 180), -1)
        ph = 160 + (t // 90) % 2 * 80        # animated signal bar
        cv2.rectangle(frame, (0, 100), (W, 112), (0, 140, 255) if ph % 160 else (60, 200, 60), -1)
        return frame

    vehicles = [
        dict(x=-180, y=180, w=230, h=120, speed=1.9, color=(200, 170, 60), plate=P["AB"]),
        dict(x=W + 200, y=440, w=200, h=105, speed=-2.2, color=(60, 130, 180), plate=P["CD"]),
        dict(x=-500, y=200, w=280, h=150, speed=1.5, color=(150, 150, 160), plate=P["MN"]),   # bus
        dict(x=W + 420, y=460, w=110, h=60, speed=-2.8, color=(100, 160, 90), plate=P["DL"]),
        dict(x=-760, y=190, w=190, h=100, speed=2.5, color=(170, 90, 90), plate=P["GH"]),
    ]
    return background, vehicles, "CG ROAD — ELLIS BRIDGE END"


# ---------------- scene: Kankaria Lake Approach (lake at top, palm strip) ----------------

@scene("../data/demo_videos/demo_lake.mp4")
def lake():
    def background(t):
        frame = np.full((H, W, 3), 45, dtype=np.uint8)
        frame[:140] = (110, 80, 40)          # water
        for wx in range(20, W, 90):          # waves
            cv2.ellipse(frame, (wx, 60 + (t // 20 + wx) % 12), (30, 6), 0, 0, 360, (140, 110, 70), 2)
        cv2.rectangle(frame, (0, 140), (W, 165), (50, 120, 50), -1)   # promenade greenery
        frame[580:] = (60, 45, 35)
        cv2.rectangle(frame, (0, 165), (W, 580), (58, 58, 60), -1)
        for x in range(0, W, 110):
            cv2.rectangle(frame, (x, 360), (x + 52, 370), (190, 190, 190), -1)
        return frame

    vehicles = [
        dict(x=-240, y=230, w=210, h=115, speed=2.7, color=(60, 120, 170), plate=P["CD"]),
        dict(x=W + 140, y=450, w=240, h=130, speed=-2.0, color=(90, 160, 80), plate=P["AB"]),
        dict(x=-520, y=240, w=100, h=58, speed=3.4, color=(140, 140, 150), plate=P["PQ"]),
        dict(x=W + 560, y=460, w=250, h=135, speed=-2.9, color=(170, 140, 60), plate=P["KL"]),
        dict(x=-880, y=225, w=220, h=118, speed=2.2, color=(120, 80, 150), plate=P["EF"]),
    ]
    return background, vehicles, "KANKARIA LAKE APPROACH"


# ---------------- scene: Maninagar Station Entrance (zebra crossing, darker asphalt) ----------------

@scene("../data/demo_videos/demo_station.mp4")
def station():
    def background(t):
        frame = np.full((H, W, 3), 35, dtype=np.uint8)
        frame[:110] = (50, 55, 70)
        cv2.rectangle(frame, (40, 25), (300, 110), (70, 75, 95), -1)   # station block
        cv2.putText(frame, "STATION", (90, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (220, 220, 220), 2)
        frame[600:] = (40, 40, 45)
        cv2.rectangle(frame, (0, 110), (W, 600), (48, 48, 52), -1)
        for k in range(9):                   # zebra crossing
            cv2.rectangle(frame, (60 + k * 130, 320), (130 + k * 130, 420), (200, 200, 200), -1)
        return frame

    vehicles = [
        dict(x=-200, y=170, w=200, h=110, speed=2.3, color=(80, 150, 190), plate=P["AB"]),
        dict(x=W + 180, y=460, w=230, h=125, speed=-1.8, color=(190, 100, 70), plate=P["CD"]),
        dict(x=-460, y=185, w=260, h=140, speed=1.6, color=(110, 110, 125), plate=P["PQ"]),
        dict(x=W + 500, y=455, w=190, h=100, speed=-2.5, color=(90, 150, 90), plate=P["MN"]),
        dict(x=-820, y=175, w=210, h=112, speed=2.9, color=(160, 160, 80), plate=P["EF"]),
    ]
    return background, vehicles, "MANINAGAR STATION ENTRANCE"


# ---------------- scene: Ring Road — Narol Circle (3 lanes, fast trucks) ----------------

@scene("../data/demo_videos/demo_ring.mp4")
def ring():
    def background(t):
        frame = np.full((H, W, 3), 50, dtype=np.uint8)
        frame[:130] = (35, 45, 35)
        frame[570:] = (35, 40, 30)
        cv2.rectangle(frame, (0, 130), (W, 570), (52, 52, 55), -1)
        for y in (270, 420):                 # two dash lines => three lanes
            for x in range(0, W, 80):
                cv2.rectangle(frame, (x, y), (x + 42, y + 9), (205, 205, 205), -1)
        cv2.circle(frame, (W - 80, 350), 70, (70, 70, 75), -1)        # circle island
        cv2.circle(frame, (W - 80, 350), 70, (180, 180, 180), 3)
        return frame

    vehicles = [
        dict(x=-260, y=160, w=250, h=130, speed=4.2, color=(70, 70, 160), plate=P["GH"]),   # truck
        dict(x=W + 200, y=310, w=200, h=105, speed=-4.6, color=(160, 60, 60), plate=P["CD"]),
        dict(x=-560, y=460, w=260, h=140, speed=3.8, color=(60, 130, 90), plate=P["AB"]),
        dict(x=W + 620, y=170, w=110, h=62, speed=-5.1, color=(130, 130, 140), plate=P["PQ"]),
        dict(x=-940, y=320, w=240, h=128, speed=4.4, color=(180, 150, 70), plate=P["KL"]),
    ]
    return background, vehicles, "RING ROAD — NAROL CIRCLE"


# ---------------- scene: University Road Junction (light daytime, parked row) ----------------

@scene("../data/demo_videos/demo_campus.mp4")
def campus():
    def background(t):
        frame = np.full((H, W, 3), 95, dtype=np.uint8)
        frame[:120] = (150, 170, 190)        # bright sky band
        cv2.rectangle(frame, (0, 120), (W, 150), (90, 140, 90), -1)
        frame[590:] = (80, 80, 85)
        cv2.rectangle(frame, (0, 150), (W, 590), (70, 70, 74), -1)
        for x in range(0, W, 95):
            cv2.rectangle(frame, (x, 360), (x + 48, 370), (215, 215, 215), -1)
        for k, px in enumerate((150, 420, 690, 960)):   # parked vehicles on footpath
            cv2.rectangle(frame, (px, 610), (px + 130, 690), (90 + k * 25, 110, 130), -1)
        return frame

    vehicles = [
        dict(x=-190, y=200, w=200, h=108, speed=2.1, color=(70, 110, 180), plate=P["AB"]),
        dict(x=W + 170, y=430, w=225, h=122, speed=-2.3, color=(150, 80, 140), plate=P["CD"]),
        dict(x=-480, y=215, w=105, h=60, speed=3.0, color=(120, 160, 120), plate=P["DL"]),
        dict(x=W + 470, y=445, w=240, h=132, speed=-1.7, color=(200, 130, 60), plate=P["EF"]),
        dict(x=-840, y=205, w=215, h=115, speed=2.6, color=(100, 100, 115), plate=P["MN"]),
    ]
    return background, vehicles, "UNIVERSITY ROAD JUNCTION"


def generate(scene_key: str, seconds: int) -> None:
    filename, builder = SCENES[scene_key]
    background, vehicles, label = builder()
    os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
    _render(filename, seconds, background, [dict(v) for v in vehicles], label)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    seconds = int(args[0]) if args else 30
    if "--all" in sys.argv:
        for key in SCENES:
            generate(key, seconds)
        print(f"Generated {len(SCENES)} demo clips.")
    else:
        generate("highway", seconds)


if __name__ == "__main__":
    main()

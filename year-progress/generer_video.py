#!/usr/bin/env python3
"""Génère la vidéo « L'année qui s'écoule » (animation + son de chargement).

Par défaut : détecte automatiquement la date du jour.

Exemples :
    python generer_video.py                         # aujourd'hui, vertical 9:16 uniquement
    python generer_video.py --date 2026-12-25       # une date précise
    python generer_video.py --format both           # vertical + horizontal
    python generer_video.py --duree 12 --sortie ./mes-videos
"""
import argparse
import calendar
import datetime
import math
import struct
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

try:
    import imageio_ffmpeg
except ImportError:  # pragma: no cover
    raise SystemExit("Installe d'abord les dépendances : pip install pillow imageio-ffmpeg")

# ----------------------------------------------------------------- français
MOIS_COURTS = ["JANV.", "FÉVR.", "MARS", "AVRIL", "MAI", "JUIN",
               "JUIL.", "AOÛT", "SEPT.", "OCT.", "NOV.", "DÉC."]
MOIS_LONGS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
              "août", "septembre", "octobre", "novembre", "décembre"]


def date_fr(d: datetime.date) -> str:
    jour = "1er" if d.day == 1 else str(d.day)
    return f"{jour} {MOIS_LONGS[d.month - 1]} {d.year}"


def restants_fr(n: int) -> str:
    if n == 0:
        return "Dernier jour de l’année !"
    return f"{n} jour restant" if n == 1 else f"{n} jours restants"


# ------------------------------------------------------------------ couleurs
BG = (5, 8, 22)
PUR = (139, 92, 246)
LIGHT = (196, 162, 255)
GREY = (40, 44, 70)
WHITE = (255, 255, 255)
MUT = (150, 150, 180)

FPS = 30
SS = 2  # sur-échantillonnage (anti-crénelage)


def police(taille, gras=True):
    essais = ([("/System/Library/Fonts/Helvetica.ttc", 1), ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 0),
               ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0), ("C:/Windows/Fonts/arialbd.ttf", 0)]
              if gras else
              [("/System/Library/Fonts/Helvetica.ttc", 0), ("/System/Library/Fonts/Supplemental/Arial.ttf", 0),
               ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0), ("C:/Windows/Fonts/arial.ttf", 0)])
    for chemin, idx in essais:
        try:
            return ImageFont.truetype(chemin, taille, index=idx)
        except OSError:
            continue
    return ImageFont.load_default()


# ------------------------------------------------------------------ mises en page
# Toutes les positions sont en pixels « réels » (avant sur-échantillonnage).
LAYOUTS = {
    "vertical": dict(
        nom="9x16", W=1080, H=1920, GX=190, STEP=28, GY=895, RS=56, R=9,
        annee=(60, 110, 230), sous=(66, 380, 36), jour=(60, 470, 30), nombre=(60, 505, 250),
        sur=(620, 600, 44), pct=(620, 500, 110), barre=(60, 760, 960), date=(60, 795, 42),
        mois=lambda GX, GY, RS, m: (60, GY + m * RS - 10, 22),
        pied=lambda GX, GY, RS: ((60, GY + 12 * RS + 20, 40), (60, GY + 12 * RS + 78, 28)),
    ),
    "horizontal": dict(
        nom="16x9", W=1920, H=1080, GX=820, STEP=32, GY=170, RS=62, R=11,
        annee=(100, 90, 190), sous=(104, 300, 30), jour=(100, 430, 28), nombre=(100, 465, 230),
        sur=(100, 720, 40), pct=(100, 790, 110), barre=(100, 940, 600), date=(100, 980, 36),
        mois=lambda GX, GY, RS, m: (GX - 120, GY + m * RS - 12, 24),
        pied=lambda GX, GY, RS: ((GX, GY + 12 * RS + 30, 44), (GX, GY + 12 * RS + 90, 28)),
    ),
}


def ease(t):
    return t * t * (3 - 2 * t)


def jours_par_mois(annee):
    return [calendar.monthrange(annee, m)[1] for m in range(1, 13)]


# ------------------------------------------------------------------ image
def rendre_image(L, date, t, t_intro, t_fill, jours):
    W, H = L["W"], L["H"]
    annee = date.year
    cible = date.timetuple().tm_yday
    total = sum(jours)
    cases = [(m, d) for m, n in enumerate(jours) for d in range(n)]

    p = 0 if t < t_intro else min(1.0, (t - t_intro) / t_fill)
    cur = cible * ease(p)
    affiche = min(cible, max(0, math.ceil(cur)))

    def s(v):
        return int(v * SS)

    im = Image.new("RGB", (W * SS, H * SS), BG)
    d = ImageDraw.Draw(im)

    a = min(1.0, t / 0.6)
    d.text((s(L["annee"][0]), s(L["annee"][1])), str(annee), font=police(s(L["annee"][2])),
           fill=tuple(int(BG[k] + (WHITE[k] - BG[k]) * a) for k in range(3)))
    d.text((s(L["sous"][0]), s(L["sous"][1])), "L’ANNÉE QUI S’ÉCOULE", font=police(s(L["sous"][2])), fill=LIGHT)
    d.text((s(L["jour"][0]), s(L["jour"][1])), "JOUR", font=police(s(L["jour"][2])), fill=MUT)
    d.text((s(L["nombre"][0]), s(L["nombre"][1])), str(affiche), font=police(s(L["nombre"][2])), fill=WHITE)
    d.text((s(L["sur"][0]), s(L["sur"][1])), f"sur {total}", font=police(s(L["sur"][2]), False), fill=MUT)
    pct = (cible if p >= 1 else cur) / total * 100
    d.text((s(L["pct"][0]), s(L["pct"][1])), f"{pct:.0f} %", font=police(s(L["pct"][2])), fill=LIGHT)

    bx, by, bw = L["barre"]
    d.rounded_rectangle((s(bx), s(by), s(bx + bw), s(by + 18)), s(9), fill=GREY)
    d.rounded_rectangle((s(bx), s(by), s(bx + max(18, bw * cur / total)), s(by + 18)), s(9), fill=PUR)

    idx = min(total - 1, max(0, affiche - 1))
    m_act, j_act = cases[idx]
    if affiche > 0:
        jour_date = datetime.date(annee, m_act + 1, j_act + 1)
        d.text((s(L["date"][0]), s(L["date"][1])), date_fr(jour_date), font=police(s(L["date"][2])), fill=WHITE)

    GX, STEP, GY, RS, R = L["GX"], L["STEP"], L["GY"], L["RS"], L["R"]
    for m in range(12):
        x, y, sz = L["mois"](GX, GY, RS, m)
        actif = affiche > 0 and m_act == m
        d.text((s(x), s(y)), MOIS_COURTS[m], font=police(s(sz)), fill=WHITE if actif else MUT)

    glow = Image.new("RGB", (W * SS, H * SS), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for k, (m, j) in enumerate(cases):
        x, y = GX + j * STEP, GY + m * RS + 4
        if k < affiche - 1:
            col = PUR
        elif k == affiche - 1:
            col = WHITE
            gd.ellipse((s(x - R - 10), s(y - R - 10), s(x + R + 10), s(y + R + 10)), fill=PUR)
        else:
            col = GREY
        if p >= 1 and k == cible - 1:
            pulse = (math.sin((t - t_intro - t_fill) * 5) + 1) / 2
            rr = R + 5 + 4 * pulse
            gd.ellipse((s(x - rr - 8), s(y - rr - 8), s(x + rr + 8), s(y + rr + 8)), fill=PUR)
            col = WHITE
        d.ellipse((s(x - R), s(y - R), s(x + R), s(y + R)), fill=col)
    glow = glow.filter(ImageFilter.GaussianBlur(s(14)))
    im = ImageChops.add(im, glow)
    d = ImageDraw.Draw(im)

    if p >= 1:
        f = min(1.0, (t - t_intro - t_fill) / 0.8)
        c1 = tuple(int(BG[k] + (WHITE[k] - BG[k]) * f) for k in range(3))
        c2 = tuple(int(BG[k] + (LIGHT[k] - BG[k]) * f) for k in range(3))
        (x1, y1, s1), (x2, y2, s2) = L["pied"](GX, GY, RS)
        reste = total - cible
        d.text((s(x1), s(y1)), f"{date_fr(date)} · {restants_fr(reste)}", font=police(s(s1)), fill=c1)
        d.text((s(x2), s(y2)), "Chaque point est un jour.", font=police(s(s2), False), fill=c2)
    return im.resize((W, H), Image.LANCZOS)


# ------------------------------------------------------------------ son
def generer_son(chemin, duree, t_intro, t_fill, cible):
    sr = 44100
    buf = [0.0] * int(sr * duree)

    def ajouter(t, fn, longueur):
        i0 = int(t * sr)
        for n in range(int(longueur * sr)):
            if i0 + n < len(buf):
                buf[i0 + n] += fn(n / sr)

    for k in range(1, cible + 1):  # un « tic » par jour, de plus en plus aigu
        lo, hi = 0.0, 1.0
        for _ in range(40):
            mid = (lo + hi) / 2
            if cible * ease(mid) < k:
                lo = mid
            else:
                hi = mid
        t = t_intro + lo * t_fill
        fq = 900 + 1500 * lo
        ajouter(t, lambda x, fq=fq: 0.22 * math.sin(2 * math.pi * fq * x) * math.exp(-x * 400), 0.025)
    for n in range(int(t_fill * sr)):  # souffle montant en fond
        x = n / sr
        fq = 180 + 420 * (x / t_fill) ** 2
        buf[int(t_intro * sr) + n] += 0.05 * math.sin(2 * math.pi * fq * x) * min(1, x / 0.2)
    for dt, fq in [(0, 880), (0.18, 1318.5)]:  # carillon final
        ajouter(t_intro + t_fill + dt,
                lambda x, fq=fq: 0.35 * (math.sin(2 * math.pi * fq * x) + 0.3 * math.sin(4 * math.pi * fq * x))
                * math.exp(-x * 3.2), 1.4)
    m = max(abs(v) for v in buf) or 1
    with wave.open(str(chemin), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, v * 0.85 / m)) * 32767)) for v in buf))


# ------------------------------------------------------------------ vidéo
def faire_video(date, fmt, duree, dossier, apercu):
    L = LAYOUTS[fmt]
    t_intro = 0.5
    t_hold = 2.0
    t_fill = max(1.0, duree - t_intro - t_hold)
    jours = jours_par_mois(date.year)
    cible = date.timetuple().tm_yday
    n = int(duree * FPS)
    ff = imageio_ffmpeg.get_ffmpeg_exe()

    base = f"annee-{date.isoformat()}-{L['nom']}"
    muet, son, sortie = dossier / f"{base}.muet.mp4", dossier / f"{base}.wav", dossier / f"{base}.mp4"
    generer_son(son, duree, t_intro, t_fill, cible)

    proc = subprocess.Popen(
        [ff, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{L['W']}x{L['H']}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(muet)],
        stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    derniere = None
    for i in range(n):
        derniere = rendre_image(L, date, i / FPS, t_intro, t_fill, jours)
        proc.stdin.write(derniere.tobytes())
    proc.stdin.close()
    proc.wait()
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(muet), "-i", str(son), "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "160k", "-t", str(duree), str(sortie)], check=True)
    muet.unlink()
    son.unlink()
    if apercu and derniere is not None:
        derniere.save(dossier / f"{base}.png")
    return sortie


def lire_date(texte):
    try:
        return datetime.date.fromisoformat(texte)
    except ValueError:
        raise argparse.ArgumentTypeError("Date invalide : utilise le format AAAA-MM-JJ (ex. 2026-12-25)")


def main():
    ap = argparse.ArgumentParser(description="Vidéo « L'année qui s'écoule » (français, avec son).")
    ap.add_argument("--date", type=lire_date, default=None,
                    help="Date au format AAAA-MM-JJ. Par défaut : la date du jour (détectée automatiquement).")
    ap.add_argument("--format", choices=["vertical", "horizontal", "both"], default="vertical",
                    help="vertical = 9:16 pour les Reels (défaut), horizontal = 16:9, both = les deux.")
    ap.add_argument("--duree", type=float, default=10.0, help="Durée en secondes (défaut : 10).")
    ap.add_argument("--sortie", type=Path, default=Path(__file__).parent / "videos", help="Dossier de sortie.")
    ap.add_argument("--apercu", action="store_true", help="Enregistre aussi l'image finale en PNG.")
    a = ap.parse_args()

    date = a.date or datetime.date.today()
    if a.duree < 4:
        raise SystemExit("La durée minimale est de 4 secondes.")
    a.sortie.mkdir(parents=True, exist_ok=True)
    total = 366 if calendar.isleap(date.year) else 365
    jour = date.timetuple().tm_yday
    print(f"Date : {date_fr(date)} · jour {jour}/{total} · {jour / total * 100:.0f} % · {restants_fr(total - jour)}")
    for fmt in (["vertical", "horizontal"] if a.format == "both" else [a.format]):
        print(f"Génération {fmt}…")
        print("  →", faire_video(date, fmt, a.duree, a.sortie, a.apercu))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Render Panini-album-style teamsheets for all 48 teams at the 2026 FIFA World Cup.

Reads data/teams.json (team metadata) and data/<CODE>.json (26-player squads),
builds one self-contained HTML page per team and screenshots it to images/<CODE>.png
with the Chromium bundled in this environment.

Usage:
    python3 generate.py            # render every team that has a data file
    python3 generate.py BEL FRA    # render specific teams
    python3 generate.py --html BEL # write the HTML only (debugging)
"""

import glob
import json
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
IMAGES = os.path.join(ROOT, "images")
AGE_REF = date(2026, 6, 11)  # tournament opening day

# ---------------------------------------------------------------- flags ----
# Stylized flag chips (simplified geometry, not exact heraldry).
# spec: list of layer tuples drawn onto a 60x40 SVG viewport.
FLAGS = {
    "MEX": [("v", ["#006341", "#FFFFFF", "#C8102E"]), ("disc", "#8C6239", 6)],
    "RSA": [("h", ["#E03C31", "#FFFFFF", "#007749", "#FFFFFF", "#001489"]), ("tri", "#FFB81C")],
    "KOR": [("h", ["#FFFFFF"]), ("taeguk",)],
    "CZE": [("h", ["#FFFFFF", "#D7141A"]), ("tri", "#11457E")],
    "CAN": [("v", ["#D80621", "#FFFFFF", "#D80621"]), ("leaf", "#D80621")],
    "BIH": [("h", ["#002F6C"]), ("tri2", "#FECB00")],
    "QAT": [("v", ["#FFFFFF", "#8A1538", "#8A1538"])],
    "SUI": [("h", ["#DA291C"]), ("cross", "#FFFFFF")],
    "BRA": [("h", ["#009739"]), ("diamond", "#FEDD00"), ("disc", "#012169", 8)],
    "MAR": [("h", ["#C8102E"]), ("star", "#006233", 30, 20, 11)],
    "HAI": [("h", ["#00209F", "#D21034"]), ("rect", "#FFFFFF", 22, 13, 16, 14)],
    "SCO": [("h", ["#0065BF"]), ("saltire", "#FFFFFF")],
    "USA": [("h", ["#B31942", "#FFFFFF", "#B31942", "#FFFFFF", "#B31942", "#FFFFFF", "#B31942"]), ("canton", "#0A3161")],
    "PAR": [("h", ["#D52B1E", "#FFFFFF", "#0038A8"]), ("disc", "#FCD116", 5)],
    "AUS": [("h", ["#012169"]), ("star", "#FFFFFF", 45, 20, 8), ("star", "#FFFFFF", 15, 28, 5)],
    "TUR": [("h", ["#E30A17"]), ("crescent", "#FFFFFF", 24, 20, 9), ("star", "#FFFFFF", 38, 20, 5)],
    "GER": [("h", ["#000000", "#DD0000", "#FFCE00"])],
    "CUW": [("h", ["#002B7F", "#002B7F", "#002B7F", "#F9E814", "#002B7F"]), ("star", "#FFFFFF", 12, 10, 5), ("star", "#FFFFFF", 20, 16, 7)],
    "CIV": [("v", ["#FF8200", "#FFFFFF", "#009A44"])],
    "ECU": [("h", ["#FFD100", "#FFD100", "#00338D", "#EF3340"]), ("disc", "#8C6239", 6)],
    "NED": [("h", ["#AE1C28", "#FFFFFF", "#21468B"])],
    "JPN": [("h", ["#FFFFFF"]), ("disc", "#BC002D", 11)],
    "SWE": [("h", ["#006AA7"]), ("nordic", "#FECC02")],
    "TUN": [("h", ["#E70013"]), ("disc", "#FFFFFF", 11), ("crescent", "#E70013", 30, 20, 8), ("star", "#E70013", 33, 20, 4)],
    "BEL": [("v", ["#000000", "#FDDA24", "#EF3340"])],
    "EGY": [("h", ["#CE1126", "#FFFFFF", "#000000"]), ("disc", "#C09300", 5)],
    "IRN": [("h", ["#239F40", "#FFFFFF", "#DA0000"]), ("disc", "#DA0000", 4)],
    "NZL": [("h", ["#012169"]), ("star", "#C8102E", 42, 12, 5), ("star", "#C8102E", 48, 22, 5), ("star", "#C8102E", 38, 28, 5)],
    "ESP": [("h", ["#AA151B", "#F1BF00", "#F1BF00", "#AA151B"])],
    "CPV": [("h", ["#003893", "#003893", "#003893", "#FFFFFF", "#CF2027", "#FFFFFF", "#003893", "#003893"]), ("star", "#F7D116", 22, 25, 6)],
    "KSA": [("h", ["#006C35"]), ("rect", "#FFFFFF", 14, 16, 32, 4), ("rect", "#FFFFFF", 20, 24, 20, 2)],
    "URU": [("h", ["#FFFFFF", "#0038A8", "#FFFFFF", "#0038A8", "#FFFFFF", "#0038A8", "#FFFFFF", "#0038A8", "#FFFFFF"]), ("canton", "#FFFFFF"), ("disc", "#FCD116", 6, 15, 10)],
    "FRA": [("v", ["#002654", "#FFFFFF", "#ED2939"])],
    "SEN": [("v", ["#00853F", "#FDEF42", "#E31B23"]), ("star", "#00853F", 30, 20, 7)],
    "IRQ": [("h", ["#CE1126", "#FFFFFF", "#000000"]), ("rect", "#007A3D", 22, 15, 16, 10)],
    "NOR": [("h", ["#BA0C2F"]), ("nordic", "#FFFFFF", 7), ("nordic", "#00205B", 4)],
    "ARG": [("h", ["#74ACDF", "#FFFFFF", "#74ACDF"]), ("disc", "#F6B40E", 6)],
    "ALG": [("v", ["#006233", "#FFFFFF"]), ("crescent", "#D21034", 30, 20, 9), ("star", "#D21034", 34, 20, 5)],
    "AUT": [("h", ["#EF3340", "#FFFFFF", "#EF3340"])],
    "JOR": [("h", ["#000000", "#FFFFFF", "#007A3D"]), ("tri", "#CE1126"), ("star", "#FFFFFF", 8, 20, 4)],
    "POR": [("v", ["#046A38", "#DA291C", "#DA291C"]), ("disc", "#FFE900", 7, 22, 20)],
    "COD": [("h", ["#007FFF"]), ("diag", "#F7D618", 13), ("diag", "#CE1021", 9), ("star", "#F7D618", 10, 9, 7)],
    "UZB": [("h", ["#0099B5", "#CE1126", "#FFFFFF", "#CE1126", "#1EB53A"]), ("crescent", "#FFFFFF", 10, 7, 5)],
    "COL": [("h", ["#FCD116", "#FCD116", "#003893", "#CE1126"])],
    "ENG": [("h", ["#FFFFFF"]), ("cross", "#CE1124")],
    "CRO": [("h", ["#FF0000", "#FFFFFF", "#171796"]), ("checker", "#FF0000")],
    "GHA": [("h", ["#CE1126", "#FCD116", "#006B3F"]), ("star", "#000000", 30, 20, 7)],
    "PAN": [("quarters", ["#FFFFFF", "#D21034", "#005293", "#FFFFFF"]),
            ("star", "#005293", 15, 10, 6), ("star", "#D21034", 45, 30, 6)],
}


def star_points(cx, cy, r):
    import math
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.42
        pts.append(f"{cx + rad * math.cos(ang):.1f},{cy + rad * math.sin(ang):.1f}")
    return " ".join(pts)


def flag_svg(code, w=60, h=40, rx=5):
    layers = FLAGS.get(code, [("h", ["#888888"])])
    parts = []
    for layer in layers:
        kind = layer[0]
        if kind == "h":
            cols = layer[1]
            bh = h / len(cols)
            for i, c in enumerate(cols):
                parts.append(f'<rect x="0" y="{i*bh:.2f}" width="{w}" height="{bh+0.5:.2f}" fill="{c}"/>')
        elif kind == "v":
            cols = layer[1]
            bw = w / len(cols)
            for i, c in enumerate(cols):
                parts.append(f'<rect x="{i*bw:.2f}" y="0" width="{bw+0.5:.2f}" height="{h}" fill="{c}"/>')
        elif kind == "quarters":
            c = layer[1]
            parts.append(f'<rect x="0" y="0" width="{w/2}" height="{h/2}" fill="{c[0]}"/>')
            parts.append(f'<rect x="{w/2}" y="0" width="{w/2}" height="{h/2}" fill="{c[1]}"/>')
            parts.append(f'<rect x="0" y="{h/2}" width="{w/2}" height="{h/2}" fill="{c[2]}"/>')
            parts.append(f'<rect x="{w/2}" y="{h/2}" width="{w/2}" height="{h/2}" fill="{c[3]}"/>')
        elif kind == "disc":
            c, r = layer[1], layer[2]
            cx = layer[3] if len(layer) > 3 else w / 2
            cy = layer[4] if len(layer) > 4 else h / 2
            parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{c}"/>')
        elif kind == "taeguk":
            parts.append(f'<circle cx="{w/2}" cy="{h/2}" r="10" fill="#CD2E3A"/>')
            parts.append(f'<path d="M {w/2-10} {h/2} A 10 10 0 0 0 {w/2+10} {h/2} A 5 5 0 0 0 {w/2} {h/2} A 5 5 0 0 1 {w/2-10} {h/2} Z" fill="#0047A0"/>')
        elif kind == "cross":
            c = layer[1]
            parts.append(f'<rect x="{w/2-5}" y="4" width="10" height="{h-8}" fill="{c}"/>')
            parts.append(f'<rect x="{w/2-14}" y="{h/2-5}" width="28" height="10" fill="{c}"/>')
            if code == "ENG":
                parts[-2] = f'<rect x="{w/2-5}" y="0" width="10" height="{h}" fill="{c}"/>'
                parts[-1] = f'<rect x="0" y="{h/2-5}" width="{w}" height="10" fill="{c}"/>'
        elif kind == "nordic":
            c = layer[1]
            t = layer[2] if len(layer) > 2 else 8
            parts.append(f'<rect x="{w*0.36-t/2}" y="0" width="{t}" height="{h}" fill="{c}"/>')
            parts.append(f'<rect x="0" y="{h/2-t/2}" width="{w}" height="{t}" fill="{c}"/>')
        elif kind == "saltire":
            c = layer[1]
            parts.append(f'<path d="M0 0 L{w} {h} M{w} 0 L0 {h}" stroke="{c}" stroke-width="9"/>')
        elif kind == "tri":
            c = layer[1]
            parts.append(f'<path d="M0 0 L{w*0.45} {h/2} L0 {h} Z" fill="{c}"/>')
        elif kind == "tri2":  # Bosnia: triangle from top edge
            c = layer[1]
            parts.append(f'<path d="M{w*0.25} 0 L{w*0.85} 0 L{w*0.25} {h} Z" fill="{c}"/>')
            for i in range(5):
                parts.append(f'<polygon points="{star_points(w*0.22 - 2 + i*7, 4 + i*8, 3.2)}" fill="#FFFFFF"/>')
        elif kind == "canton":
            c = layer[1]
            parts.append(f'<rect x="0" y="0" width="{w*0.45}" height="{h*0.5}" fill="{c}"/>')
        elif kind == "rect":
            c, x, y, rw, rh = layer[1], layer[2], layer[3], layer[4], layer[5]
            parts.append(f'<rect x="{x}" y="{y}" width="{rw}" height="{rh}" fill="{c}"/>')
        elif kind == "diag":
            c, t = layer[1], layer[2]
            parts.append(f'<path d="M0 {h} L{w} 0" stroke="{c}" stroke-width="{t}"/>')
        elif kind == "star":
            c, cx, cy, r = layer[1], layer[2], layer[3], layer[4]
            parts.append(f'<polygon points="{star_points(cx, cy, r)}" fill="{c}"/>')
        elif kind == "crescent":
            c, cx, cy, r = layer[1], layer[2], layer[3], layer[4]
            parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{c}"/>')
            parts.append(f'<circle cx="{cx + r*0.45}" cy="{cy}" r="{r*0.82}" fill="__BG__"/>')
        elif kind == "leaf":
            c = layer[1]
            parts.append(f'<path d="M{w/2} 8 L{w/2+4} 15 L{w/2+10} 13 L{w/2+7} 21 L{w/2+12} 24 L{w/2} 32 L{w/2-12} 24 L{w/2-7} 21 L{w/2-10} 13 L{w/2-4} 15 Z" fill="{c}"/>')
        elif kind == "checker":
            c = layer[1]
            s = 4.4
            for r_ in range(3):
                for c_ in range(5):
                    if (r_ + c_) % 2 == 0:
                        parts.append(f'<rect x="{w/2-11+c_*s:.1f}" y="{h/2-6.6+r_*s:.1f}" width="{s}" height="{s}" fill="{c}"/>')
                    else:
                        parts.append(f'<rect x="{w/2-11+c_*s:.1f}" y="{h/2-6.6+r_*s:.1f}" width="{s}" height="{s}" fill="#FFFFFF"/>')
    body = "".join(parts)
    # crescent cutout needs flag base color under it: use first color of first layer
    base = layers[0][1][0] if isinstance(layers[0][1], list) else "#FFFFFF"
    if code == "TUN":
        base = "#FFFFFF"
    if code == "ALG":
        base = "#FFFFFF" if False else "__SPLIT__"
    body = body.replace("__BG__", base if code != "ALG" else "#FFFFFF")
    return (f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" '
            f'style="border-radius:{rx}px;overflow:hidden;display:block;width:100%;height:100%">'
            f'<defs><clipPath id="fc{code}"><rect x="0" y="0" width="{w}" height="{h}" rx="{rx}"/></clipPath></defs>'
            f'<g clip-path="url(#fc{code})">{body}</g></svg>')


# ------------------------------------------------------------- clubs ------
# Primary/secondary colors per club (exact-name match with data files).
# Used to draw a small generic crest chip — NOT official club logos.
CLUB_COLORS = {}


def load_club_colors():
    path = os.path.join(DATA, "clubs.json")
    if os.path.exists(path):
        with open(path) as f:
            CLUB_COLORS.update(json.load(f))


def crest_svg(club):
    c1, c2 = CLUB_COLORS.get(club, ("#9aa4a8", "#5c666a"))
    return (f'<svg viewBox="0 0 20 24" xmlns="http://www.w3.org/2000/svg" '
            f'style="display:block;width:100%;height:100%">'
            f'<path d="M10 1 L19 4 L19 13 C19 19 15 22 10 23.5 C5 22 1 19 1 13 L1 4 Z" fill="{c1}" stroke="#ffffff" stroke-width="1.2"/>'
            f'<path d="M10 1 L19 4 L19 13 C19 19 15 22 10 23.5 Z" fill="{c2}"/>'
            f'</svg>')


# ----------------------------------------------------------- silhouette ----
def silhouette_svg(kit1, kit2, number=None):
    """Stylized player bust: dark head, kit-colored jersey with contrast collar/stripes.
    If `number` is given it is printed on the jersey chest in the contrast color."""
    num = ""
    if number is not None:
        num = (f'<text x="100" y="168" text-anchor="middle" font-family="Liberation Sans, Arial" '
               f'font-size="52" font-weight="bold" fill="{kit2}">{number}</text>')
    return f'''<svg viewBox="0 0 200 210" xmlns="http://www.w3.org/2000/svg" style="display:block;width:100%;height:100%">
  <ellipse cx="100" cy="52" rx="30" ry="34" fill="#2b2b33"/>
  <rect x="86" y="78" width="28" height="22" rx="8" fill="#2b2b33"/>
  <path d="M100 96 C 60 96 34 118 28 152 L 24 210 L 176 210 L 172 152 C 166 118 140 96 100 96 Z" fill="{kit1}"/>
  <path d="M100 96 C 92 96 86 97 80 99 L 100 124 L 120 99 C 114 97 108 96 100 96 Z" fill="{kit2}"/>
  <path d="M62 103 C 48 111 38 124 33 140 L 30 178 L 46 178 L 48 138 C 52 122 58 112 66 105 Z" fill="{kit2}" opacity="0.9"/>
  <path d="M138 103 C 152 111 162 124 167 140 L 170 178 L 154 178 L 152 138 C 148 122 142 112 134 105 Z" fill="{kit2}" opacity="0.9"/>
  {num}
</svg>'''


# ------------------------------------------------------------- helpers ----
def fmt_dob(dob):
    if not dob:
        return "—"
    y, m, d = dob.split("-")
    return f"{int(d)}-{int(m)}-{y}"


def calc_age(dob):
    if not dob:
        return None
    y, m, d = (int(x) for x in dob.split("-"))
    b = date(y, m, d)
    return AGE_REF.year - b.year - ((AGE_REF.month, AGE_REF.day) < (b.month, b.day))


def fmt_h(h):
    return f"{h:.2f} m" if h else "—"


def fmt_w(w):
    return f"{w:g} kg" if w else "—"


POS_LABEL = {"GK": "GOALKEEPER", "DF": "DEFENDER", "MF": "MIDFIELDER", "FW": "FORWARD"}


def rating_badge(r, big=False):
    cls = "rate big" if big else "rate"
    if r is None:
        return f'<div class="{cls} unrated">–</div>'
    return f'<div class="{cls}">{r}</div>'


# -------------------------------------------------------------- page ------
def team_html(meta, squad, group_mates):
    kit1, kit2 = meta["kit_primary"], meta["kit_secondary"]
    players = squad["players"]
    rated = [p["fc26"] for p in players if p.get("fc26") is not None]
    avg = sum(rated) / len(rated) if rated else 0

    cards = []
    for p in players:
        age = calc_age(p.get("dob"))
        age_txt = f"{age} yrs" if age is not None else "—"
        first, _, last = p["name"].rpartition(" ")
        if not first:
            first, last = "", p["name"]
        cards.append(f'''
    <div class="card">
      <div class="card-top">
        <div class="fifa-mark">FIFA<br>WORLD CUP 26™</div>
        <div class="sticker-no">{meta["code"]}&nbsp;{p["sticker"]}</div>
        <div class="chip-flag">{flag_svg(meta["code"])}</div>
      </div>
      <div class="art">
        <div class="sil">{silhouette_svg(kit1, kit2, p["sticker"])}</div>
        {rating_badge(p.get("fc26"))}
      </div>
      <div class="pos">{POS_LABEL[p["position"]]}</div>
      <div class="pname"><span class="pfirst">{first}</span> <span class="plast">{last}</span></div>
      <div class="pill stats">{fmt_dob(p.get("dob"))} &nbsp;|&nbsp; {age_txt} &nbsp;|&nbsp; {fmt_h(p.get("height_m"))} &nbsp;|&nbsp; {fmt_w(p.get("weight_kg"))}</div>
      <div class="pill club"><span class="crest">{crest_svg(p["club"])}</span><span class="clubname">{p["club"].upper()} ({p["club_country"]})</span></div>
    </div>''')

    coach_card = f'''
    <div class="card special coach">
      <div class="card-top"><div class="fifa-mark">FIFA<br>WORLD CUP 26™</div><div class="sticker-no">COACH</div>
      <div class="chip-flag">{flag_svg(meta["code"])}</div></div>
      <div class="art"><div class="sil">{silhouette_svg("#3a3a44", "#e8e4da")}</div></div>
      <div class="pos">HEAD COACH</div>
      <div class="pname"><span class="plast">{squad.get("coach", "—")}</span></div>
      <div class="pill club">{meta["name"].upper()}</div>
    </div>'''

    avg_card = f'''
    <div class="card special gold">
      <div class="goldtitle">TEAM<br>RATING</div>
      <div class="goldavg">{avg:.1f}</div>
      <div class="goldsub">EA SPORTS FC 26 OVERALL</div>
      <div class="goldsub2">{len(rated)}/26 PLAYERS RATED</div>
    </div>'''

    mates = "".join(f'<div class="gm">{m}</div>' for m in group_mates)
    group_card = f'''
    <div class="card special group">
      <div class="grouptitle">GROUP</div>
      <div class="groupletter">{meta["group"]}</div>
      <div class="gmates"><div class="gm self">{meta["name"]}</div>{mates}</div>
    </div>'''

    logo_card = '''
    <div class="card special logo">
      <div class="wc-logo"><span class="wc26a">2</span><span class="wc26b">6</span></div>
      <div class="wc-txt">FIFA WORLD CUP<br>CANADA · MEXICO · USA</div>
      <div class="road">ROAD TO 2026</div>
    </div>'''

    flag_big = flag_svg(meta["code"], rx=8)

    return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ width:1500px; font-family:"Liberation Sans", Arial, sans-serif; background:#E8542F; }}
  .page {{ position:relative; padding:34px 40px 24px; overflow:hidden;
          background:
            radial-gradient(1200px 500px at 85% -5%, #F7B32B 0%, rgba(247,179,43,0) 60%),
            radial-gradient(900px 600px at -10% 30%, #D93A26 0%, rgba(217,58,38,0) 55%),
            radial-gradient(700px 500px at 50% 105%, #F7B32B 0%, rgba(247,179,43,0) 55%),
            linear-gradient(160deg, #E8542F 0%, #E2492B 45%, #EE7A33 100%); }}
  .deco {{ position:absolute; font-weight:bold; color:rgba(255,255,255,0.10); font-size:420px; letter-spacing:-30px; line-height:0.8; user-select:none; }}

  header {{ position:relative; display:flex; align-items:center; gap:28px; margin-bottom:26px; }}
  .we {{ font-size:54px; font-weight:bold; font-style:italic; letter-spacing:2px; color:#111;
        text-transform:uppercase; line-height:0.95; }}
  .team {{ font-size:84px; font-weight:bold; letter-spacing:1px; color:#fff; text-transform:uppercase; line-height:0.95;
          text-shadow:4px 4px 0 rgba(140,20,10,0.55); }}
  .fed {{ margin-top:10px; font-size:19px; color:#fff; max-width:560px; line-height:1.25; }}
  .hflag {{ width:120px; height:80px; flex:0 0 auto; box-shadow:0 4px 14px rgba(0,0,0,0.35); border-radius:8px; }}
  .hspacer {{ flex:1; }}
  .havg {{ flex:0 0 auto; text-align:center; background:linear-gradient(160deg,#F5D06F,#E3A93C 55%,#C98A1E);
          border-radius:14px; padding:14px 26px; box-shadow:0 6px 16px rgba(0,0,0,0.3); }}
  .havg .n {{ font-size:56px; font-weight:bold; color:#3a2705; line-height:1; }}
  .havg .t {{ font-size:15px; font-weight:bold; color:#5a3d08; letter-spacing:2px; }}
  .havg .s {{ font-size:12px; color:#6b4a0c; margin-top:3px; }}

  .grid {{ position:relative; display:grid; grid-template-columns:repeat(5, 1fr); gap:14px; }}

  .card {{ background:#AEDEDA; border-radius:10px; padding:10px 12px 12px; position:relative;
          box-shadow:0 3px 10px rgba(0,0,0,0.28); display:flex; flex-direction:column; }}
  .card-top {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:4px; }}
  .fifa-mark {{ font-size:9px; font-weight:bold; color:#fff; background:#0f6f6a; padding:3px 5px; border-radius:4px; line-height:1.1; }}
  .sticker-no {{ font-size:15px; font-weight:bold; color:#0f6f6a; letter-spacing:1px; }}
  .chip-flag {{ width:34px; height:23px; }}

  .art {{ position:relative; height:162px; margin:2px 0 6px;
         background:radial-gradient(90px 70px at 50% 92%, rgba(232,84,47,0.28), rgba(232,84,47,0) 70%); }}
  .sil {{ position:absolute; left:50%; transform:translateX(-50%); bottom:0; width:158px; height:158px;
         filter:drop-shadow(0 3px 4px rgba(0,0,0,0.28)); }}
  .rate {{ position:absolute; left:6px; bottom:2px; width:46px; height:52px; display:flex; align-items:center; justify-content:center;
          font-size:24px; font-weight:bold; color:#3a2705;
          background:linear-gradient(160deg,#F5D06F,#E3A93C 60%,#C98A1E);
          clip-path:polygon(50% 0, 100% 14%, 100% 78%, 50% 100%, 0 78%, 0 14%); box-shadow:0 2px 6px rgba(0,0,0,0.3); }}
  .rate.unrated {{ background:linear-gradient(160deg,#cfd4d6,#a7b0b3); color:#5c666a; }}

  .pos {{ font-size:10px; font-weight:bold; letter-spacing:2px; color:#0f6f6a; }}
  .pname {{ min-height:44px; display:flex; align-items:center; gap:5px; flex-wrap:wrap; line-height:1.05; margin:1px 0 6px; }}
  .pfirst {{ font-size:17px; color:#123f3c; }}
  .plast {{ font-size:19px; font-weight:bold; color:#123f3c; text-transform:uppercase; }}
  .pill {{ border-radius:20px; font-size:11.5px; padding:4px 9px; text-align:center; white-space:nowrap; }}
  .stats {{ background:#0f6f6a; color:#dff4f2; margin-bottom:5px; font-weight:bold; }}
  .club {{ background:#D93A26; color:#fff; font-weight:bold; display:flex; align-items:center; justify-content:center; gap:5px; font-size:10.5px; padding:4px 7px; }}
  .club .crest {{ flex:0 0 auto; width:15px; height:18px; }}
  .club .clubname {{ min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}

  .special {{ align-items:center; justify-content:center; text-align:center; }}
  .gold {{ background:linear-gradient(160deg,#F5D06F,#E3A93C 55%,#C98A1E); }}
  .goldtitle {{ font-size:22px; font-weight:bold; letter-spacing:4px; color:#5a3d08; line-height:1.1; }}
  .goldavg {{ font-size:92px; font-weight:bold; color:#3a2705; line-height:1.05; }}
  .goldsub {{ font-size:12px; font-weight:bold; color:#5a3d08; letter-spacing:1px; }}
  .goldsub2 {{ font-size:11px; color:#6b4a0c; margin-top:4px; }}
  .group {{ background:#123f3c; }}
  .grouptitle {{ font-size:16px; font-weight:bold; letter-spacing:5px; color:#AEDEDA; }}
  .groupletter {{ font-size:96px; font-weight:bold; color:#F7B32B; line-height:1; margin:2px 0 8px; }}
  .gm {{ font-size:15px; color:#dff4f2; padding:2px 0; }}
  .gm.self {{ font-weight:bold; color:#F7B32B; }}
  .logo {{ background:#fff; }}
  .wc-logo {{ font-size:110px; font-weight:bold; font-style:italic; line-height:0.9; letter-spacing:-6px; }}
  .wc26a {{ color:#D93A26; }} .wc26b {{ color:#F7B32B; }}
  .wc-txt {{ font-size:13px; font-weight:bold; color:#123f3c; letter-spacing:1px; margin-top:8px; line-height:1.4; }}
  .road {{ margin-top:8px; font-size:11px; font-weight:bold; color:#fff; background:#123f3c; border-radius:14px; padding:4px 12px; letter-spacing:2px; }}
  .coach .pname {{ justify-content:center; }}

  footer {{ position:relative; display:flex; justify-content:space-between; align-items:center; margin-top:20px;
           color:#fff; font-weight:bold; letter-spacing:3px; font-size:16px; }}
  footer .small {{ font-size:10px; font-weight:normal; letter-spacing:0.5px; opacity:0.85; text-align:right; line-height:1.4; }}
</style></head>
<body><div class="page">
  <div class="deco" style="right:-60px; top:120px;">26</div>
  <div class="deco" style="left:-80px; bottom:40px;">26</div>
  <header>
    <div>
      <div class="we">We are</div>
      <div class="team">{meta["name"]}</div>
      <div class="fed">{meta["federation"]}</div>
    </div>
    <div class="hflag">{flag_big}</div>
    <div class="hspacer"></div>
    <div class="havg">
      <div class="t">TEAM RATING</div>
      <div class="n">{avg:.1f}</div>
      <div class="s">EA FC 26 · {len(rated)}/26 rated</div>
    </div>
  </header>
  <div class="grid">
    {''.join(cards)}
    {coach_card}
    {avg_card}
    {group_card}
    {logo_card}
  </div>
  <footer>
    <div>ROAD TO FIFA WORLD CUP 2026™</div>
    <div class="small">Unofficial fan-made concept in the style of a sticker album · squads as announced 2 June 2026<br>
    Ratings: EA SPORTS FC 26 overalls · "—" = not verified / not in game · silhouettes, not player likenesses</div>
  </footer>
</div></body></html>'''


# --------------------------------------------------------------- main -----
def find_chromium():
    for pat in ["/opt/pw-browsers/chromium-*/chrome-linux/chrome", "/opt/pw-browsers/chromium"]:
        hits = sorted(glob.glob(pat))
        for h in hits:
            if os.path.isfile(h) and os.access(h, os.X_OK):
                return h
    return None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    html_only = "--html" in sys.argv

    load_club_colors()
    with open(os.path.join(DATA, "teams.json")) as f:
        registry = json.load(f)
    teams = {t["code"]: t for t in registry["teams"]}

    codes = args or [c for c in teams if os.path.exists(os.path.join(DATA, f"{c}.json"))]
    os.makedirs(IMAGES, exist_ok=True)

    pages = []
    for code in codes:
        meta = teams[code]
        with open(os.path.join(DATA, f"{code}.json")) as f:
            squad = json.load(f)
        mates = [t["name"] for t in registry["teams"] if t["group"] == meta["group"] and t["code"] != code]
        html = team_html(meta, squad, mates)
        hpath = os.path.join(IMAGES, f"{code}.html")
        with open(hpath, "w") as f:
            f.write(html)
        pages.append((code, hpath))
        print(f"built HTML {code}")

    if html_only:
        return

    from playwright.sync_api import sync_playwright
    exe = find_chromium()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1500, "height": 1200}, device_scale_factor=1)
        for code, hpath in pages:
            page.goto("file://" + hpath)
            page.wait_for_timeout(120)
            page.screenshot(path=os.path.join(IMAGES, f"{code}.png"), full_page=True)
            print(f"rendered {code}.png")
        browser.close()

    for _, hpath in pages:
        os.remove(hpath)


if __name__ == "__main__":
    main()

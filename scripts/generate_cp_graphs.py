#!/usr/bin/env python3
"""Generate Tokyo Night-themed SVG rating graphs for Codeforces and CodeChef."""

from __future__ import annotations

import datetime as dt
import html
import json
import math
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

CF_HANDLE = "Benzene-C6H6"
CC_HANDLE = "prathameshk28"

# Vibrant Electric Cyan & Magenta Dark palette
BG = "#0f172a"
BORDER = "#1e3a5f"
TITLE = "#22d3ee"
TEXT = "#f8fafc"
MUTED = "#94a3b8"
GRID = "#1e293b"
ACCENT_CF = "#22d3ee"
ACCENT_CC = "#f472b6"
PEAK_COLOR = "#facc15"


def fetch_text(url: str) -> str:
    ua = "Mozilla/5.0 (compatible; GitHubProfileGraphBot/1.0)"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": ua,
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError:
        res = subprocess.run(
            ["curl", "-fsSL", "--max-time", "20", "-A", ua, url],
            check=True,
            capture_output=True,
            text=True,
        )
        return res.stdout


def fetch_codeforces(handle: str) -> dict:
    info = json.loads(
        fetch_text(f"https://codeforces.com/api/user.info?handles={handle}")
    )["result"][0]
    rating_data = json.loads(
        fetch_text(f"https://codeforces.com/api/user.rating?handle={handle}")
    )["result"]

    points = [
        {
            "ts": int(item["ratingUpdateTimeSeconds"]),
            "rating": int(item["newRating"]),
            "label": item.get("contestName", ""),
        }
        for item in rating_data
    ]
    current = int(info.get("rating", points[-1]["rating"] if points else 0))
    max_rating = int(info.get("maxRating", max((p["rating"] for p in points), default=0)))
    max_rank = str(info.get("maxRank", "unrated")).title()
    return {
        "platform": "Codeforces",
        "handle": handle,
        "badge": f"Max: {max_rank}",
        "badge_color": "#38bdae",
        "current": current,
        "max": max_rating,
        "contests": len(points),
        "points": points,
        "line_color": ACCENT_CF,
        "bands": [
            (0, 1200, "#9aa5ce"),      # Newbie
            (1200, 1400, "#73daca"),   # Pupil
            (1400, 1600, "#7dcfff"),   # Specialist
            (1600, 1900, "#7aa2f7"),   # Expert
            (1900, 2100, "#bb9af7"),   # CM
        ],
    }


def cc_stars(rating: int) -> tuple[str, str]:
    if rating >= 2500:
        return "7★", "#f7768e"
    if rating >= 2200:
        return "6★", "#ff9e64"
    if rating >= 2000:
        return "5★", "#e0af68"
    if rating >= 1800:
        return "4★", "#bb9af7"
    if rating >= 1600:
        return "3★", "#7aa2f7"
    if rating >= 1400:
        return "2★", "#73daca"
    return "1★", "#9aa5ce"


def fetch_codechef(handle: str) -> dict:
    page = fetch_text(f"https://www.codechef.com/users/{handle}")
    m_arr = re.search(r"var all_rating\s*=\s*(\[.*?\]);", page)
    if not m_arr:
        raise RuntimeError("Could not locate CodeChef rating history in profile HTML")
    raw = json.loads(m_arr.group(1))
    points = []
    for item in raw:
        y = int(item["getyear"])
        mo = int(item["getmonth"])
        d = int(item["getday"])
        ts = int(dt.datetime(y, mo, d, tzinfo=dt.timezone.utc).timestamp())
        points.append(
            {
                "ts": ts,
                "rating": int(item["rating"]),
                "label": item.get("name", item.get("code", "")),
            }
        )
    current = points[-1]["rating"] if points else 0
    m_max = re.search(r"Highest Rating\s*(\d+)", page)
    max_rating = int(m_max.group(1)) if m_max else max((p["rating"] for p in points), default=0)
    stars, badge_color = cc_stars(max(current, max_rating))
    return {
        "platform": "CodeChef",
        "handle": handle,
        "badge": stars,
        "badge_color": badge_color,
        "current": current,
        "max": max_rating,
        "contests": len(points),
        "points": points,
        "line_color": ACCENT_CC,
        "bands": [
            (0, 1400, "#9aa5ce"),      # 1*
            (1400, 1600, "#73daca"),   # 2*
            (1600, 1800, "#7aa2f7"),   # 3*
            (1800, 2000, "#bb9af7"),   # 4*
            (2000, 2200, "#e0af68"),   # 5*
        ],
    }


def render_svg(data: dict) -> str:
    w, h = 540, 240
    pad_l, pad_r, pad_t, pad_b = 48, 22, 66, 30
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b

    points = data["points"]
    if not points:
        raise RuntimeError(f"No contest data for {data['platform']}")

    ratings = [p["rating"] for p in points]
    min_r = min(ratings)
    max_r = max(ratings)

    # Round y-axis bounds nicely to nearest 100 with breathing room
    y_min = max(0, int(math.floor((min_r - 120) / 100.0) * 100))
    y_max = int(math.ceil((max_r + 140) / 100.0) * 100)
    if y_max - y_min < 400:
        y_max = y_min + 400

    ts_list = [p["ts"] for p in points]
    t_min, t_max = min(ts_list), max(ts_list)
    if t_min == t_max:
        t_min -= 86400
        t_max += 86400

    def x_pos(ts: int) -> float:
        return pad_l + (ts - t_min) / (t_max - t_min) * plot_w

    def y_pos(r: float) -> float:
        return pad_t + plot_h - (r - y_min) / (y_max - y_min) * plot_h

    grad_id = f"area-{data['platform'].lower()}"
    clip_id = f"clip-{data['platform'].lower()}"

    # Rating tier bands clipped to plot area
    band_rects = []
    for lo, hi, color in data["bands"]:
        b_lo = max(lo, y_min)
        b_hi = min(hi, y_max)
        if b_hi > b_lo:
            y1 = y_pos(b_hi)
            y2 = y_pos(b_lo)
            band_rects.append(
                f'<rect x="{pad_l}" y="{y1:.1f}" width="{plot_w}" height="{y2 - y1:.1f}" '
                f'fill="{color}" fill-opacity="0.08"/>'
            )

    # Y gridlines (every 200 or 100 depending on span)
    step = 200 if (y_max - y_min) >= 600 else 100
    grid_lines = []
    y_val = (y_min // step) * step
    while y_val <= y_max:
        if y_min <= y_val <= y_max:
            yp = y_pos(y_val)
            grid_lines.append(
                f'<line x1="{pad_l}" y1="{yp:.1f}" x2="{w - pad_r}" y2="{yp:.1f}" '
                f'stroke="{GRID}" stroke-width="1" stroke-dasharray="3,3"/>'
            )
            grid_lines.append(
                f'<text x="{pad_l - 8}" y="{yp + 3.5:.1f}" text-anchor="end" '
                f'font-size="10" fill="{MUTED}">{y_val}</text>'
            )
        y_val += step

    # X axis ticks (4 evenly spaced dates)
    x_ticks = []
    for i in range(4):
        ts_tick = int(t_min + (t_max - t_min) * i / 3)
        xp = x_pos(ts_tick)
        label = dt.datetime.fromtimestamp(ts_tick, tz=dt.timezone.utc).strftime("%b '%y")
        anchor = "start" if i == 0 else ("end" if i == 3 else "middle")
        x_ticks.append(
            f'<text x="{xp:.1f}" y="{h - 10}" text-anchor="{anchor}" '
            f'font-size="10" fill="{MUTED}">{label}</text>'
        )

    coords = [(x_pos(p["ts"]), y_pos(p["rating"]), p["rating"]) for p in points]
    line_d = " ".join(
        f"{'M' if idx == 0 else 'L'} {cx:.1f} {cy:.1f}"
        for idx, (cx, cy, _) in enumerate(coords)
    )
    area_d = (
        f"{line_d} L {coords[-1][0]:.1f} {pad_t + plot_h:.1f} "
        f"L {coords[0][0]:.1f} {pad_t + plot_h:.1f} Z"
    )

    peak_idx = max(range(len(points)), key=lambda i: points[i]["rating"])
    peak_x, peak_y, peak_r = coords[peak_idx]

    dots = []
    for idx, (cx, cy, r) in enumerate(coords):
        is_peak = idx == peak_idx
        is_last = idx == len(coords) - 1
        fill = PEAK_COLOR if is_peak else data["line_color"]
        radius = 4.2 if (is_peak or is_last) else 2.8
        dots.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius}" '
            f'fill="{fill}" stroke="{BG}" stroke-width="1.5"/>'
        )

    # Peak label positioned cleanly inside plot
    peak_anchor = "middle"
    if peak_x > w - pad_r - 45:
        peak_anchor = "end"
    elif peak_x < pad_l + 45:
        peak_anchor = "start"
    peak_label_y = max(pad_t + 12, peak_y - 9)

    title_txt = html.escape(f"{data['platform']} · {data['handle']}")
    badge_txt = html.escape(data["badge"])
    stats_txt = html.escape(
        f"Current: {data['current']}   ·   Peak: {data['max']}   ·   Contests: {data['contests']}"
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{title_txt} Rating Graph">
  <defs>
    <linearGradient id="{grad_id}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{data['line_color']}" stop-opacity="0.28"/>
      <stop offset="100%" stop-color="{data['line_color']}" stop-opacity="0.01"/>
    </linearGradient>
    <clipPath id="{clip_id}">
      <rect x="{pad_l}" y="{pad_t}" width="{plot_w}" height="{plot_h}" rx="4"/>
    </clipPath>
  </defs>
  <style>
    text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
  </style>

  <rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="10" fill="{BG}" stroke="{BORDER}" stroke-width="1"/>

  <!-- Header -->
  <text x="20" y="30" font-size="15" font-weight="700" fill="{TITLE}">{title_txt}</text>
  <rect x="{w - 108}" y="14" width="88" height="22" rx="11" fill="{data['badge_color']}" fill-opacity="0.16" stroke="{data['badge_color']}" stroke-opacity="0.55" stroke-width="1"/>
  <text x="{w - 64}" y="29" text-anchor="middle" font-size="11" font-weight="600" fill="{data['badge_color']}">{badge_txt}</text>
  <text x="20" y="50" font-size="11.5" font-weight="500" fill="{TEXT}">{stats_txt}</text>

  <!-- Plot background bands -->
  <g clip-path="url(#{clip_id})">
    {''.join(band_rects)}
  </g>

  <!-- Gridlines & axes -->
  {''.join(grid_lines)}
  <line x1="{pad_l}" y1="{pad_t + plot_h}" x2="{w - pad_r}" y2="{pad_t + plot_h}" stroke="{BORDER}" stroke-width="1"/>
  {''.join(x_ticks)}

  <!-- Area & Rating Curve -->
  <path d="{area_d}" fill="url(#{grad_id})" clip-path="url(#{clip_id})"/>
  <path d="{line_d}" fill="none" stroke="{data['line_color']}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>

  <!-- Points & Peak Marker -->
  {''.join(dots)}
  <text x="{peak_x:.1f}" y="{peak_label_y:.1f}" text-anchor="{peak_anchor}" font-size="10.5" font-weight="700" fill="{PEAK_COLOR}">★ {peak_r}</text>
</svg>
'''


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    jobs = [
        ("codeforces-rating.svg", lambda: fetch_codeforces(CF_HANDLE)),
        ("codechef-rating.svg", lambda: fetch_codechef(CC_HANDLE)),
    ]
    had_error = False
    for filename, fetcher in jobs:
        out_path = ASSETS / filename
        try:
            data = fetcher()
            svg = render_svg(data)
            out_path.write_text(svg, encoding="utf-8")
            print(f"Updated {out_path} ({data['platform']}: current={data['current']}, max={data['max']}, contests={data['contests']})")
        except Exception as exc:
            print(f"Warning: failed to update {filename}: {exc}", file=sys.stderr)
            if not out_path.exists():
                had_error = True
    return 1 if had_error else 0


if __name__ == "__main__":
    raise SystemExit(main())

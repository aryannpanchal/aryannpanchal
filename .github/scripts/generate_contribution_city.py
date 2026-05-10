#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import math
import os
import random
import urllib.request
from html import escape
from pathlib import Path


QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks {
          contributionDays {
            date
            contributionCount
            contributionLevel
            color
          }
        }
      }
    }
  }
}
"""


def fetch_contributions(user):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
      return demo_contributions()

    body = json.dumps({"query": QUERY, "variables": {"login": user}}).encode("utf-8")
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "contribution-city-generator",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if payload.get("errors"):
        raise RuntimeError(payload["errors"])

    weeks = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [
        {**day, "week": week_index, "day": day_index}
        for week_index, week in enumerate(weeks)
        for day_index, day in enumerate(week["contributionDays"])
    ]


def demo_contributions():
    today = dt.date.today()
    start = today - dt.timedelta(days=364)
    random.seed(42)
    days = []
    for index in range(365):
        date = start + dt.timedelta(days=index)
        wave = max(0, math.sin(index / 13) + random.random() - 0.55)
        count = int(wave * 9)
        days.append(
            {
                "date": date.isoformat(),
                "contributionCount": count,
                "contributionLevel": "NONE",
                "color": "#0e4429" if count else "#161b22",
                "week": index // 7,
                "day": index % 7,
            }
        )
    return days


def polygon(points, fill, opacity=1, stroke="#0f172a", stroke_width=0.6):
    point_string = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return (
        f'<polygon points="{point_string}" fill="{fill}" opacity="{opacity}" '
        f'stroke="{stroke}" stroke-width="{stroke_width}" />'
    )


def shade(hex_color, factor):
    color = hex_color.lstrip("#")
    red = int(color[0:2], 16)
    green = int(color[2:4], 16)
    blue = int(color[4:6], 16)
    red = max(0, min(255, int(red * factor)))
    green = max(0, min(255, int(green * factor)))
    blue = max(0, min(255, int(blue * factor)))
    return f"#{red:02x}{green:02x}{blue:02x}"


def floors_for_count(count):
    if count <= 0:
        return 0
    return max(1, min(18, int(math.ceil(math.sqrt(count) * 2.2))))


def render_tile(cx, cy, tile_w, tile_h, fill):
    return polygon(
        [
            (cx, cy - tile_h / 2),
            (cx + tile_w / 2, cy),
            (cx, cy + tile_h / 2),
            (cx - tile_w / 2, cy),
        ],
        fill,
        opacity=0.78,
        stroke="#1e293b",
        stroke_width=0.45,
    )


def render_building(cx, cy, tile_w, tile_h, floors, count, date, color):
    floor_h = 5.6
    height = floors * floor_h
    top_y = cy - height
    top = [
        (cx, top_y - tile_h / 2),
        (cx + tile_w / 2, top_y),
        (cx, top_y + tile_h / 2),
        (cx - tile_w / 2, top_y),
    ]
    right = [
        (cx + tile_w / 2, top_y),
        (cx + tile_w / 2, cy),
        (cx, cy + tile_h / 2),
        (cx, top_y + tile_h / 2),
    ]
    left = [
        (cx - tile_w / 2, top_y),
        (cx, top_y + tile_h / 2),
        (cx, cy + tile_h / 2),
        (cx - tile_w / 2, cy),
    ]

    pieces = [
        f"<g><title>{escape(date)}: {count} contributions, {floors} floors</title>",
        polygon(left, shade(color, 0.62), opacity=0.94, stroke="#0f172a", stroke_width=0.5),
        polygon(right, shade(color, 0.78), opacity=0.96, stroke="#0f172a", stroke_width=0.5),
        polygon(top, shade(color, 1.12), opacity=0.98, stroke="#67e8f9", stroke_width=0.55),
    ]

    for floor in range(1, floors):
        y = cy - floor * floor_h
        pieces.append(
            f'<line x1="{cx - tile_w / 2:.1f}" y1="{y:.1f}" x2="{cx:.1f}" y2="{y + tile_h / 2:.1f}" '
            'stroke="#e0f2fe" stroke-opacity="0.14" stroke-width="0.45" />'
        )
        pieces.append(
            f'<line x1="{cx + tile_w / 2:.1f}" y1="{y:.1f}" x2="{cx:.1f}" y2="{y + tile_h / 2:.1f}" '
            'stroke="#e0f2fe" stroke-opacity="0.12" stroke-width="0.45" />'
        )

    pieces.append("</g>")
    return "\n".join(pieces)


def render_city(days, user):
    tile_w = 15
    tile_h = 8
    x_gap = 9.4
    y_gap = 9.4
    origin_x = 550
    origin_y = 84
    width = 1100
    height = 470

    sorted_days = sorted(days, key=lambda day: (day["week"] + day["day"], day["week"]))
    buildings = []
    total = sum(day["contributionCount"] for day in days)
    active_days = sum(1 for day in days if day["contributionCount"] > 0)
    max_count = max((day["contributionCount"] for day in days), default=0)

    for day in sorted_days:
        week = day["week"]
        weekday = day["day"]
        cx = origin_x + (week - weekday) * x_gap
        cy = origin_y + (week + weekday) * y_gap / 2
        count = day["contributionCount"]
        floors = floors_for_count(count)
        color = day.get("color") if count else "#182033"
        if floors:
            buildings.append(render_building(cx, cy, tile_w, tile_h, floors, count, day["date"], color))
        else:
            buildings.append(render_tile(cx, cy, tile_w, tile_h, "#111827"))

    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">{escape(user)} contribution city</title>
  <desc id="desc">An isometric city generated from GitHub contributions. Each building represents one day and each floor represents contribution intensity.</desc>
  <defs>
    <radialGradient id="glow" cx="50%" cy="35%" r="70%">
      <stop offset="0%" stop-color="#164e63" stop-opacity="0.42"/>
      <stop offset="55%" stop-color="#0f172a" stop-opacity="0.22"/>
      <stop offset="100%" stop-color="#020617" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="sky" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#020617"/>
      <stop offset="50%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#082f49"/>
    </linearGradient>
    <filter id="softShadow" x="-20%" y="-20%" width="140%" height="160%">
      <feDropShadow dx="0" dy="18" stdDeviation="18" flood-color="#020617" flood-opacity="0.55"/>
    </filter>
  </defs>
  <rect width="1100" height="470" rx="24" fill="url(#sky)"/>
  <rect width="1100" height="470" rx="24" fill="url(#glow)"/>
  <g opacity="0.35">
    <circle cx="100" cy="70" r="1.2" fill="#e0f2fe"/>
    <circle cx="220" cy="42" r="1" fill="#bae6fd"/>
    <circle cx="890" cy="80" r="1.1" fill="#e0f2fe"/>
    <circle cx="1010" cy="120" r="1" fill="#bae6fd"/>
    <circle cx="760" cy="36" r="1.1" fill="#e0f2fe"/>
  </g>
  <text x="40" y="55" fill="#e0f2fe" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="24" font-weight="700">Contribution City</text>
  <text x="40" y="84" fill="#94a3b8" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="13">Generated from {escape(user)}'s GitHub activity</text>
  <g font-family="Inter, Segoe UI, Arial, sans-serif" font-size="12" fill="#cbd5e1">
    <text x="40" y="126">{total:,} contributions</text>
    <text x="40" y="148">{active_days} active days</text>
    <text x="40" y="170">{max_count} max in a day</text>
  </g>
  <g filter="url(#softShadow)">
    {"".join(buildings)}
  </g>
</svg>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    days = fetch_contributions(args.user)
    svg = render_city(days, args.user)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Generates a dark, cinematic "Mission Telemetry" SVG card from live GitHub data:
- owned repos, total stars, contributions in the last year
- monthly contribution trajectory (last 12 months)
- top languages by public code volume

Requires:
  GH_TOKEN      - a token with public read access (repo contents + read:user).
                  A classic PAT works reliably; the default Actions GITHUB_TOKEN
                  sometimes lacks scope for the GraphQL contributionsCollection query.
  GH_USERNAME   - the GitHub username to report on.

Output:
  assets/telemetry.svg
"""

import os
import sys
import datetime
import requests

GITHUB_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
USERNAME = os.environ.get("GH_USERNAME")

if not GITHUB_TOKEN or not USERNAME:
    print("ERROR: GH_TOKEN and GH_USERNAME must be set as environment variables.", file=sys.stderr)
    sys.exit(1)

REST_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}
GQL_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Content-Type": "application/json",
}

LANG_COLORS = {
    "TypeScript": "#3b82f6",
    "JavaScript": "#eab308",
    "Python": "#38bdf8",
    "CSS": "#8b5cf6",
    "HTML": "#f97316",
    "Java": "#f59e0b",
    "C++": "#ec4899",
    "C": "#a3a3a3",
    "PLpgSQL": "#94a3b8",
    "Jupyter Notebook": "#f97316",
    "Shell": "#22c55e",
}
DEFAULT_LANG_COLORS = ["#38bdf8", "#6366f1", "#a78bfa", "#f472b6", "#94a3b8"]

MONTH_ABBR = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def get_user_info():
    r = requests.get(f"https://api.github.com/users/{USERNAME}", headers=REST_HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def get_repos():
    repos = []
    page = 1
    while True:
        r = requests.get(
            f"https://api.github.com/users/{USERNAME}/repos",
            headers=REST_HEADERS,
            params={"per_page": 100, "page": page, "type": "owner"},
            timeout=30,
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos


def get_languages(repos):
    totals = {}
    for repo in repos:
        if repo.get("fork"):
            continue
        r = requests.get(repo["languages_url"], headers=REST_HEADERS, timeout=30)
        if r.status_code != 200:
            continue
        for lang, byte_count in r.json().items():
            totals[lang] = totals.get(lang, 0) + byte_count
    return totals


def get_contribution_calendar():
    today = datetime.datetime.utcnow()
    one_year_ago = today - datetime.timedelta(days=365)
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    variables = {
        "login": USERNAME,
        "from": one_year_ago.strftime("%Y-%m-%dT00:00:00Z"),
        "to": today.strftime("%Y-%m-%dT23:59:59Z"),
    }
    r = requests.post(
        "https://api.github.com/graphql",
        headers=GQL_HEADERS,
        json={"query": query, "variables": variables},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def monthly_trajectory(calendar):
    """Bucket daily contribution counts into the last 12 calendar months."""
    today = datetime.date.today()
    buckets = {}
    order = []
    for i in range(11, -1, -1):
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1
        key = (year, month)
        buckets[key] = 0
        order.append(key)

    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            d = datetime.date.fromisoformat(day["date"])
            key = (d.year, d.month)
            if key in buckets:
                buckets[key] += day["contributionCount"]

    labels = [MONTH_ABBR[k[1] - 1] for k in order]
    values = [buckets[k] for k in order]
    return labels, values


def top_languages(totals, top_n=5):
    total_bytes = sum(totals.values()) or 1
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    result = []
    for i, (lang, byte_count) in enumerate(ranked):
        pct = round((byte_count / total_bytes) * 100)
        color = LANG_COLORS.get(lang, DEFAULT_LANG_COLORS[i % len(DEFAULT_LANG_COLORS)])
        result.append({"name": lang, "pct": pct, "color": color})
    return result


def build_svg(owned_repos, year_signals, stars, month_labels, month_values, languages):
    W, H = 1600, 760
    panel_x, panel_y = 40, 100
    panel_w, panel_h = W - 80, H - 180

    # ---- grid lines (background texture) ----
    grid_lines = []
    for gx in range(panel_x, panel_x + panel_w, 40):
        grid_lines.append(f'<line x1="{gx}" y1="{panel_y}" x2="{gx}" y2="{panel_y + panel_h}" stroke="#141c2e" stroke-width="1"/>')
    for gy in range(panel_y, panel_y + panel_h, 40):
        grid_lines.append(f'<line x1="{panel_x}" y1="{gy}" x2="{panel_x + panel_w}" y2="{gy}" stroke="#141c2e" stroke-width="1"/>')

    # ---- monthly bar chart ----
    chart_x = 120
    chart_w = 940
    chart_baseline = 500
    chart_top = 340
    n = len(month_values)
    slot_w = chart_w / n
    bar_w = 34
    max_val = max(month_values) if max(month_values, default=0) > 0 else 1

    bars = []
    labels_svg = []
    for i, (label, val) in enumerate(zip(month_labels, month_values)):
        cx = chart_x + i * slot_w + slot_w / 2
        h = 6 if val == 0 else max(10, (val / max_val) * (chart_baseline - chart_top))
        y = chart_baseline - h
        bars.append(
            f'<rect x="{cx - bar_w/2:.1f}" y="{y:.1f}" width="{bar_w}" height="{h:.1f}" rx="8" '
            f'fill="url(#barGradient)" opacity="{1.0 if val > 0 else 0.35}"/>'
        )
        labels_svg.append(
            f'<text x="{cx:.1f}" y="{chart_baseline + 28}" text-anchor="middle" '
            f'font-family="Arial, sans-serif" font-size="13" letter-spacing="1" fill="#64748b">{label}</text>'
        )

    # ---- language signal bar + list ----
    lang_x = 1140
    lang_bar_y = 300
    lang_bar_w = 400
    lang_bar_h = 14
    seg_x = lang_x
    segments = []
    for lang in languages:
        seg_w = max(2, (lang["pct"] / 100) * lang_bar_w)
        segments.append(
            f'<rect x="{seg_x:.1f}" y="{lang_bar_y}" width="{seg_w:.1f}" height="{lang_bar_h}" '
            f'rx="{lang_bar_h/2}" fill="{lang["color"]}"/>'
        )
        seg_x += seg_w + 4

    lang_rows = []
    row_y = lang_bar_y + 60
    for lang in languages:
        lang_rows.append(f'''
          <circle cx="{lang_x + 8}" cy="{row_y - 6}" r="6" fill="{lang['color']}"/>
          <text x="{lang_x + 28}" y="{row_y}" font-family="Arial, sans-serif" font-size="20" font-weight="700" fill="#e2e8f0">{lang['name']}</text>
          <text x="{lang_x + lang_bar_w}" y="{row_y}" text-anchor="end" font-family="Arial, sans-serif" font-size="20" font-weight="700" fill="#94a3b8">{lang['pct']}%</text>
        ''')
        row_y += 44

    updated = datetime.date.today().isoformat()

    svg = f'''<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="barGradient" x1="0" y1="1" x2="0" y2="0">
      <stop offset="0%" stop-color="#6366f1"/>
      <stop offset="100%" stop-color="#38bdf8"/>
    </linearGradient>
    <linearGradient id="bgGlow" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0b1120"/>
      <stop offset="100%" stop-color="#050810"/>
    </linearGradient>
  </defs>

  <rect width="{W}" height="{H}" fill="#05070d"/>

  <g font-family="Arial, sans-serif">
    <text x="44" y="52" font-size="34" font-weight="800" fill="#f8fafc">Mission telemetry</text>
    <line x1="44" y1="76" x2="{W-44}" y2="76" stroke="#1e293b" stroke-width="1"/>
  </g>

  <rect x="{panel_x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" rx="18" fill="url(#bgGlow)" stroke="#1e293b" stroke-width="1"/>
  <clipPath id="panelClip"><rect x="{panel_x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" rx="18"/></clipPath>
  <g clip-path="url(#panelClip)">
    {''.join(grid_lines)}
  </g>

  <g font-family="Arial, sans-serif">
    <text x="{panel_x+40}" y="{panel_y+50}" font-size="14" font-weight="700" letter-spacing="2" fill="#7c9cff">LIVE MISSION TELEMETRY</text>
    <circle cx="{panel_x+panel_w-140}" cy="{panel_y+46}" r="5" fill="#22d3ee">
      <animate attributeName="opacity" values="1;0.35;1" dur="2.4s" repeatCount="indefinite"/>
      <animate attributeName="r" values="5;7;5" dur="2.4s" repeatCount="indefinite"/>
    </circle>
    <text x="{panel_x+panel_w-40}" y="{panel_y+51}" text-anchor="end" font-size="13" letter-spacing="2" fill="#64748b">SYNCED</text>

    <text x="{panel_x+40}" y="{panel_y+140}" font-size="60" font-weight="800" fill="#ffffff">{owned_repos}</text>
    <text x="{panel_x+40}" y="{panel_y+170}" font-size="14" letter-spacing="2" fill="#94a3b8">OWNED REPOS</text>

    <text x="{panel_x+300}" y="{panel_y+140}" font-size="60" font-weight="800" fill="#ffffff">{year_signals}</text>
    <text x="{panel_x+300}" y="{panel_y+170}" font-size="14" letter-spacing="2" fill="#94a3b8">YEAR SIGNALS</text>

    <text x="{panel_x+590}" y="{panel_y+140}" font-size="60" font-weight="800" fill="#ffffff">{stars}</text>
    <text x="{panel_x+590}" y="{panel_y+170}" font-size="14" letter-spacing="2" fill="#94a3b8">STARS EARNED</text>

    <text x="{panel_x+40}" y="{panel_y+240}" font-size="28" font-weight="800" fill="#f1f5f9">Contribution trajectory</text>
    <text x="{panel_x+40}" y="{panel_y+268}" font-size="14" letter-spacing="2" fill="#64748b">LAST 12 MONTHS</text>

    {''.join(bars)}
    {''.join(labels_svg)}

    <line x1="{lang_x-40}" y1="{panel_y+60}" x2="{lang_x-40}" y2="{panel_y+panel_h-60}" stroke="#1e293b" stroke-width="1"/>

    <text x="{lang_x}" y="{panel_y+140}" font-size="28" font-weight="800" fill="#f1f5f9">Language signal</text>
    <text x="{lang_x}" y="{panel_y+168}" font-size="14" letter-spacing="2" fill="#64748b">BY PUBLIC CODE VOLUME</text>

    {''.join(segments)}
    {''.join(lang_rows)}

    <text x="{panel_x+40}" y="{panel_y+panel_h-30}" font-size="13" letter-spacing="1" fill="#475569">PUBLIC GITHUB DATA · UPDATED {updated}</text>
    <text x="{panel_x+panel_w-40}" y="{panel_y+panel_h-30}" text-anchor="end" font-size="13" letter-spacing="1" fill="#475569">OWNED ASSET · NO LIVE CARD SERVICE</text>
  </g>

  <text x="{W/2}" y="{H-30}" text-anchor="middle" font-family="Arial, sans-serif" font-size="18" fill="#94a3b8">Generated from public GitHub data and refreshed automatically.</text>
</svg>'''
    return svg


def main():
    print(f"Fetching data for {USERNAME}...")
    user_info = get_user_info()
    repos = get_repos()
    languages = get_languages(repos)
    calendar = get_contribution_calendar()

    owned_repos = user_info.get("public_repos", len(repos))
    stars = sum(r.get("stargazers_count", 0) for r in repos if not r.get("fork"))
    year_signals = calendar["totalContributions"]
    month_labels, month_values = monthly_trajectory(calendar)
    langs = top_languages(languages)

    svg = build_svg(owned_repos, year_signals, stars, month_labels, month_values, langs)

    os.makedirs("assets", exist_ok=True)
    with open("assets/telemetry.svg", "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"Wrote assets/telemetry.svg — repos={owned_repos} stars={stars} contributions={year_signals}")


if __name__ == "__main__":
    main()

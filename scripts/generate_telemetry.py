#!/usr/bin/env python3
"""
Generates a green terminal SVG card from live GitHub data:
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
import json
from urllib.request import Request, urlopen
from html import escape

GITHUB_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
USERNAME = os.environ.get("GH_USERNAME")

REST_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}
GQL_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Content-Type": "application/json",
}

MONTH_ABBR = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def github_json(url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(url, data=data, headers=GQL_HEADERS if data else REST_HEADERS)
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def get_user_info():
    return github_json(f"https://api.github.com/users/{USERNAME}")


def get_repos():
    repos = []
    page = 1
    while True:
        batch = github_json(
            f"https://api.github.com/users/{USERNAME}/repos?per_page=100&page={page}&type=owner"
        )
        if not batch:
            return repos
        repos.extend(batch)
        page += 1


def get_languages(repos):
    totals = {}
    for repo in repos:
        if repo.get("fork"):
            continue
        for lang, byte_count in github_json(repo["languages_url"]).items():
            totals[lang] = totals.get(lang, 0) + byte_count
    return totals


def get_contribution_calendar():
    today = datetime.datetime.now(datetime.timezone.utc)
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
    data = github_json("https://api.github.com/graphql", {"query": query, "variables": variables})
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
    for lang, byte_count in ranked:
        pct = round((byte_count / total_bytes) * 100)
        result.append({"name": lang, "pct": pct})
    return result


def build_svg(owned_repos, year_signals, stars, month_labels, month_values, languages):
    """Render a readable, self-contained terminal card. No remote image assets."""
    width, height = 1000, 650
    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">Public GitHub activity</title>
<desc id="desc">{owned_repos} public repositories including forks, {year_signals} contributions in the last year, {stars} stars on non-fork repositories. Language percentages measure public code volume, excluding forks.</desc>
<rect x="1" y="1" width="998" height="648" rx="14" fill="#020b06" stroke="#225c36"/>
<path d="M1 54H999M34 212H966M520 244V572" stroke="#225c36"/>
<g font-family="Menlo,Consolas,monospace">
<text x="30" y="34" font-size="17" fill="#86efac">$ github --public --last-year</text>
''']
    for x, value, label in [(34, owned_repos, "PUBLIC REPOS / WITH FORKS"),
                            (360, year_signals, "YEAR CONTRIBUTIONS"),
                            (686, stars, "STARS / NON-FORK REPOS")]:
        parts.append(f'''<text x="{x}" y="136" font-size="54" font-weight="700" fill="#4ade80">{value}</text>
<text x="{x}" y="177" font-size="15" fill="#a0c7ac">{label}</text>''')
    parts.append('''<text x="34" y="262" font-size="20" fill="#dcfce7">Contribution history</text>
<text x="550" y="262" font-size="20" fill="#dcfce7">Language / code volume</text>''')
    # Labels and bars occupy separate vertical bands, even in the busiest month.
    peak = max(month_values, default=0) or 1
    for i, (label, value) in enumerate(zip(month_labels, month_values)):
        x = 40 + i * 38
        bar_height = (value / peak) * 190
        parts.append(f'''<rect x="{x}" y="{510-bar_height:.1f}" width="20" height="{bar_height:.1f}" rx="2" fill="#4ade80"><title>{escape(label)}: {value}</title></rect>
<text x="{x+10}" y="538" text-anchor="middle" font-size="12" fill="#a0c7ac">{escape(label)}</text>''')
    for i, lang in enumerate(languages):
        y = 314 + i * 51
        parts.append(f'''<text x="550" y="{y}" font-size="17" fill="#dcfce7">{escape(lang['name'])}</text>
<text x="960" y="{y}" text-anchor="end" font-size="17" fill="#86efac">{lang['pct']}%</text>
<rect x="550" y="{y+12}" width="410" height="5" fill="#12341f"/>
<rect x="550" y="{y+12}" width="{410*lang['pct']/100:.1f}" height="5" fill="#4ade80"/>''')
    updated = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    parts.append(f'''<path d="M34 586H966" stroke="#225c36"/>
<text x="34" y="620" font-size="14" fill="#a0c7ac">PUBLIC DATA / UPDATED {updated} UTC</text>
<text x="966" y="620" text-anchor="end" font-size="14" fill="#86efac">SCHEDULED DAILY</text>
</g></svg>''')
    return "\n".join(parts)


def main():
    if not GITHUB_TOKEN or not USERNAME:
        print("ERROR: GH_TOKEN and GH_USERNAME must be set as environment variables.", file=sys.stderr)
        sys.exit(1)
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

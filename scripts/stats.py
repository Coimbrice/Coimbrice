"""Render the "top languages by commit" card for the profile README.

Runs daily in GitHub Actions. Public card services only see public commits and are often
down, so the card is generated here from the GraphQL API instead.

Usage: GITHUB_TOKEN=... python scripts/stats.py OUTPUT_DIR
"""

import json
import math
import os
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

LOGIN = "Coimbrice"
API_URL = "https://api.github.com/graphql"

# Markup and build files say little about what I write.
IGNORED_LANGUAGES = {"HTML", "CSS", "Makefile"}
# Config, not projects.
IGNORED_REPOS = {"dotfiles"}
TOP_LANGUAGES = 5

# Commits are credited to the repository's primary language, the same approximation
# github-profile-summary-cards uses. They are counted from each repository's history because
# contributionsCollection only reports private commits as a total, without the repository.
ID_QUERY = "query($login: String!) { user(login: $login) { id } }"
QUERY = """
query($login: String!, $id: ID!, $since: GitTimestamp!) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100) {
      nodes {
        name
        primaryLanguage { name color }
        defaultBranchRef {
          target { ... on Commit { history(author: {id: $id}, since: $since) { totalCount } } }
        }
      }
    }
  }
}
"""

BACKGROUND = "#0d1117"
BORDER = "#30363d"
TEXT = "#c9d1d9"
TITLE = "#58a6ff"
MUTED = "#8b949e"
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
WIDTH = 420
HEIGHT = 200
LEGEND_TOP = 70
LEGEND_STEP = 22
DONUT_X = 320
DONUT_Y = 110
DONUT_RADIUS = 48
DONUT_STROKE = 22


def query(token: str, text: str, variables: dict) -> dict:
    body = json.dumps({"query": text, "variables": variables}).encode()
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]


def fetch(token: str, since: date) -> list[dict]:
    user_id = query(token, ID_QUERY, {"login": LOGIN})["user"]["id"]
    variables = {"login": LOGIN, "id": user_id, "since": f"{since.isoformat()}T00:00:00Z"}
    return query(token, QUERY, variables)["user"]["repositories"]["nodes"]


def commit_count(repo: dict) -> int:
    branch = repo["defaultBranchRef"]
    return branch["target"]["history"]["totalCount"] if branch else 0


def top_languages(repos: list[dict]) -> list[tuple[str, str, float]]:
    commits: dict[str, int] = {}
    colors: dict[str, str] = {}
    for repo in repos:
        language = repo["primaryLanguage"]
        count = commit_count(repo)
        if repo["name"] in IGNORED_REPOS or not language or not count:
            continue
        name = language["name"]
        if name in IGNORED_LANGUAGES:
            continue
        commits[name] = commits.get(name, 0) + count
        colors[name] = language["color"] or MUTED

    total = sum(commits.values())
    if not total:
        return []
    ranked = sorted(commits.items(), key=lambda item: item[1], reverse=True)[:TOP_LANGUAGES]
    return [(name, colors[name], 100 * count / total) for name, count in ranked]


def donut(languages: list[tuple[str, str, float]]) -> str:
    # Each slice is a dashed circle; the dash length is the slice, the offset is where it starts.
    circumference = 2 * math.pi * DONUT_RADIUS
    shown = sum(percent for _, _, percent in languages)
    parts = [
        f'<circle cx="{DONUT_X}" cy="{DONUT_Y}" r="{DONUT_RADIUS}" fill="none" '
        f'stroke="{BORDER}" stroke-width="{DONUT_STROKE}"/>'
    ]
    start = 0.0
    for _, color, percent in languages:
        # Scale to the languages shown, so the ring closes even when the tail is cut off.
        length = circumference * percent / shown
        parts.append(
            f'<circle cx="{DONUT_X}" cy="{DONUT_Y}" r="{DONUT_RADIUS}" fill="none" '
            f'stroke="{color}" stroke-width="{DONUT_STROKE}" '
            f'stroke-dasharray="{length:.2f} {circumference - length:.2f}" '
            f'stroke-dashoffset="{-start:.2f}" '
            f'transform="rotate(-90 {DONUT_X} {DONUT_Y})"/>'
        )
        start += length
    return "".join(parts)


def render_languages(languages: list[tuple[str, str, float]], updated: date) -> str:
    legend = []
    for index, (name, color, percent) in enumerate(languages):
        y = LEGEND_TOP + index * LEGEND_STEP
        legend.append(
            f'<rect x="24" y="{y - 10}" width="12" height="12" rx="2" fill="{color}"/>'
            f'<text x="44" y="{y}">{escape(name)}</text>'
            f'<text x="190" y="{y}" class="muted" text-anchor="end">{percent:.0f}%</text>'
        )
    ring = donut(languages) if languages else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}">'
        f"<style>text{{font-family:{FONT};font-size:14px;fill:{TEXT}}}"
        f".title{{font-size:18px;fill:{TITLE}}}.muted{{fill:{MUTED}}}"
        f".small{{font-size:11px;fill:{MUTED}}}</style>"
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="8" '
        f'fill="{BACKGROUND}" stroke="{BORDER}"/>'
        '<text x="24" y="38" class="title">Top languages by commit</text>'
        f"{''.join(legend)}{ring}"
        f'<text x="24" y="{HEIGHT - 16}" class="small">'
        f"Last 12 months · updated {updated.isoformat()}</text>"
        "</svg>\n"
    )


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: stats.py OUTPUT_DIR")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set")

    today = date.today()
    languages = top_languages(fetch(token, today - timedelta(days=365)))
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    (out / "languages.svg").write_text(render_languages(languages, today), encoding="utf-8")


if __name__ == "__main__":
    main()

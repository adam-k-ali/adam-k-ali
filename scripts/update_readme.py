"""Refresh the generated sections of README.md.

Publishes only aggregates (language percentages, a repo count) so nothing
about private repos' names, commit messages or push times is exposed.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.github.com"
TOP_LANGUAGES = 6
ACTIVE_WINDOW_DAYS = 30


def get(url, token):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(req) as resp:
        return json.load(resp), resp.headers.get("Link", "")


def own_repos(token):
    """All repos the token owns (public and private), excluding forks."""
    repos, page = [], 1
    while True:
        batch, _ = get(
            f"{API}/user/repos?affiliation=owner&per_page=100&page={page}", token
        )
        if not batch:
            return [r for r in repos if not r["fork"]]
        repos += batch
        page += 1


def language_totals(repos, token):
    totals = {}
    for repo in repos:
        langs, _ = get(f"{API}/repos/{repo['full_name']}/languages", token)
        for name, size in langs.items():
            totals[name] = totals.get(name, 0) + size
    return totals


def active_repo_count(repos):
    cutoff = datetime.now(timezone.utc) - timedelta(days=ACTIVE_WINDOW_DAYS)
    return sum(
        1 for r in repos
        if datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00")) >= cutoff
    )


def render_languages(totals):
    total = sum(totals.values())
    if not total:
        return "_No language data yet._"
    top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:TOP_LANGUAGES]
    return "\n".join(f"- {name}: {round(size * 100 / total)}%" for name, size in top)


def render_activity(count):
    noun = "repository" if count == 1 else "repositories"
    return f"Active across **{count}** {noun} over the past month."


def replace_section(text, name, body):
    pattern = re.compile(
        rf"(<!--START_SECTION:{name}-->).*?(<!--END_SECTION:{name}-->)", re.S
    )
    if not pattern.search(text):
        sys.exit(f"Missing markers for section '{name}' in README.md")
    return pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(2)}", text)


def main():
    token = os.environ["GH_TOKEN"]
    repos = own_repos(token)

    with open("README.md", encoding="utf-8") as f:
        readme = f.read()
    readme = replace_section(readme, "languages", render_languages(language_totals(repos, token)))
    readme = replace_section(readme, "activity", render_activity(active_repo_count(repos)))
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme)


if __name__ == "__main__":
    main()

"""Pick the merchants to show in the demo, by a rule, so every rehearsal uses the same ones.

Purpose: the demo needs four cases that tell the story. Searching 4,000 rows live is slow and
    risky; this prints the ids to open, and why each one was chosen.
Owner role: D (full-stack).
Implements: Phase 12 (a small script that picks demo merchants).

    python deploy/pick_demo_merchants.py                       the API on this laptop
    python deploy/pick_demo_merchants.py --details             also print each score's top reasons
    python deploy/pick_demo_merchants.py --more 4              four other ids that fit each case
    python deploy/pick_demo_merchants.py --json                machine-readable
    python deploy/pick_demo_merchants.py --url https://YOUR.DOMAIN/api --basic-auth-env SITE_LOGIN

The four cases (the synthetic data is seeded, so the same ids come out on every machine):

1. Strong: the merchant most like the typical Strong one (score nearest the median of those with
   the best coverage). A normal good case.
2. Review with a low-score warning: the lowest score among merchants with enough coverage to be
   judged. Shows the warning, and is the natural place to show an officer's override.
3. Needs more info with a HIGH score: the highest score among merchants whose coverage is below
   the line. Shows that low coverage means "Needs more info" whatever the score.
4. No consent: the first merchant without a valid consent. Shows that nothing is scored.

Reading the queue is not audited. `--details` reads three score cards, and the API writes one audit
entry for each score it shows. Standard library only; needs the API running.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import statistics
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8000"
DEFAULT_USER = "viewer-1"  # read-only demo user
TIMEOUT_SECONDS = 60
LOW_SCORE_LINE = 70  # only used to describe a pick; the API's own flag is what the screen shows


class PickError(Exception):
    """The queue has no merchant for a case, or the API cannot be reached."""


def ranked(queue: list[dict]) -> dict[str, list[dict]]:
    """For each case, the merchants that fit it, best first. The first is the pick.

    Deterministic: the same queue gives the same order. Raises PickError when a case has no
    merchant (for example a queue of a public data mode, which is empty).
    """
    scored = [row for row in queue if row.get("consent_valid") and row.get("band")]
    if not scored:
        raise PickError(
            "The queue has no scored merchant. Is the API running the synthetic data mode?"
        )
    strong = [row for row in scored if row["band"] == "Strong"]
    review = [row for row in scored if row["band"] == "Review"]
    thin = [row for row in scored if row["band"] == "Needs more info"]
    for name, rows in (("Strong", strong), ("Review", review), ("Needs more info", thin)):
        if not rows:
            raise PickError(f"No merchant in the band '{name}' in this queue.")
    no_consent = [row for row in queue if not row.get("consent_valid")]
    if not no_consent:
        raise PickError("Every merchant in this queue has a consent.")

    best_coverage = max(row["coverage"] for row in strong)
    full = [row for row in strong if row["coverage"] == best_coverage]
    middle = statistics.median(row["score"] for row in full)
    return {
        "strong": sorted(full, key=lambda r: (abs(r["score"] - middle), r["merchant_id"])),
        "review_low_score": sorted(review, key=lambda r: (r["score"], r["merchant_id"])),
        "needs_more_info": sorted(thin, key=lambda r: (-r["score"], r["merchant_id"])),
        "no_consent": sorted(no_consent, key=lambda r: r["merchant_id"]),
    }


def why(key: str, row: dict, queue: list[dict]) -> str:
    """One sentence on why a merchant is the pick for its case."""
    if key == "strong":
        return (
            f"a typical Strong case: the best coverage ({row['coverage']:.0%}) and a score "
            "nearest the median of those"
        )
    if key == "review_low_score":
        return (
            "the lowest score among merchants with enough coverage: shows the low-score "
            "warning and is the place to show an officer's override"
        )
    if key == "needs_more_info":
        return (
            f"score {row['score']} but coverage {row['coverage']:.0%}: low coverage means "
            "'Needs more info' whatever the score"
        )
    return "no valid consent: no score, no coverage, no band, nothing computed"


def pick(queue: list[dict], more: int = 0) -> dict[str, dict]:
    """The four demo merchants from a review queue (the rows of GET /merchants).

    With `more`, each pick also lists that many other merchants that fit the same case
    (`also_fits`), in case the first one's reasons do not suit the story.
    """
    picks = {}
    for key, rows in ranked(queue).items():
        picks[key] = {**rows[0], "why": why(key, rows[0], queue)}
        if more:
            picks[key]["also_fits"] = [row["merchant_id"] for row in rows[1 : more + 1]]
    return picks


def api_get(base_url: str, path: str, token: str, basic_auth: str | None = None):
    headers = {"X-Demo-Token": token}
    if basic_auth:
        headers["Authorization"] = "Basic " + base64.b64encode(basic_auth.encode()).decode()
    request = urllib.request.Request(base_url.rstrip("/") + path, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8")[:200]
        raise PickError(f"{path} answered {error.code}: {detail}") from None
    except (urllib.error.URLError, OSError) as error:
        raise PickError(
            f"Cannot reach the API at {base_url} ({error}). Start it: python tasks.py api"
        ) from None


def describe(label: str, row: dict) -> str:
    if row.get("score") is None:
        facts = "no score, no coverage, no band (no valid consent)"
    else:
        warning = "  LOW-SCORE WARNING" if row["score"] < LOW_SCORE_LINE else ""
        facts = f"score {row['score']}, coverage {row['coverage']:.0%}, {row['band']}{warning}"
    place = ", ".join(part for part in (row.get("district"), row.get("town_tier")) if part)
    return (
        f"{label}\n  {row['merchant_id']}  ({place or 'place not given'})\n  {facts}\n"
        f"  why: {row['why']}\n  open: /merchants/{row['merchant_id']}"
    )


LABELS = {
    "strong": "1. STRONG",
    "review_low_score": "2. REVIEW, low-score warning",
    "needs_more_info": "3. NEEDS MORE INFO, high score",
    "no_consent": "4. NO CONSENT",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pick the demo merchants.", allow_abbrev=False)
    parser.add_argument("--url", default=DEFAULT_URL, help="the API's address")
    parser.add_argument("--token", default=DEFAULT_USER, help="a demo user id")
    parser.add_argument(
        "--basic-auth-env",
        help="name of an environment variable that holds user:password for the site's password "
        "(never type the password in the command)",
    )
    parser.add_argument("--details", action="store_true", help="print each score's top reasons")
    parser.add_argument(
        "--more", type=int, default=0, metavar="N", help="also list N other merchants per case"
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    basic = os.environ.get(args.basic_auth_env, "") if args.basic_auth_env else None
    try:
        queue = api_get(args.url, "/merchants", args.token, basic)
        picks = pick(queue, args.more)
        if args.details:
            for key, row in picks.items():
                if row.get("consent_valid"):
                    path = f"/merchants/{row['merchant_id']}/score"
                    card = api_get(args.url, path, args.token, basic)
                    row["helps"] = [r["sentence_en"] for r in card["reasons_positive"]]
                    row["holds_back"] = [r["sentence_en"] for r in card["reasons_negative"]]
    except PickError as error:
        print(f"NOT PICKED: {error}")
        return 1
    if args.json:
        print(json.dumps(picks, indent=2, ensure_ascii=False))
        return 0
    print(f"Demo merchants ({len(queue)} in the queue):\n")
    for key, row in picks.items():
        print(describe(LABELS[key], row))
        if row.get("also_fits"):
            print(f"  also fits: {', '.join(row['also_fits'])}")
        for sentence in row.get("helps", []):
            print(f"    helps: {sentence}")
        for sentence in row.get("holds_back", []):
            print(f"    holds back: {sentence}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

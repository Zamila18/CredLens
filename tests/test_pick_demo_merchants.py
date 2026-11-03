"""Tests for the demo merchant picker (deploy/pick_demo_merchants.py).

Owner role: D (full-stack).
Implements: Phase 12 (a small script that picks demo merchants).

The rule is tried on hand-made queues, and the whole command against a stand-in API.
"""

from __future__ import annotations

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from accounts_seed import headers_for, seed_accounts, seed_person  # noqa: F401

from deploy import pick_demo_merchants as picker


def row(merchant_id, score=None, coverage=None, band=None, consent=True):
    return {
        "merchant_id": merchant_id,
        "district": "Dhaka",
        "town_tier": "metro",
        "score": score,
        "coverage": coverage,
        "band": band,
        "consent_valid": consent,
        "status": "pending",
    }


QUEUE = [
    row("M1", 99, 0.65, "Strong"),
    row("M2", 93, 0.65, "Strong"),
    row("M3", 95, 0.65, "Strong"),
    row("M4", 97, 0.45, "Strong"),  # less coverage: not the typical Strong case
    row("M5", 66, 0.45, "Review"),
    row("M6", 52, 0.55, "Review"),
    row("M7", 80, 1.0, "Review"),
    row("M8", 91, 0.35, "Needs more info"),
    row("M9", 96, 0.35, "Needs more info"),
    row("M10", 50, 0.2, "Needs more info"),
    row("M12", None, None, None, consent=False),
    row("M11", None, None, None, consent=False),
]


def test_the_four_cases_are_chosen_by_the_rule():
    picks = picker.pick(QUEUE)
    assert list(picks) == ["strong", "review_low_score", "needs_more_info", "no_consent"]
    # Strong with the best coverage, the score nearest the median (95) of M1, M2, M3
    assert picks["strong"]["merchant_id"] == "M3"
    # the lowest score among those with enough coverage to be judged
    assert picks["review_low_score"]["merchant_id"] == "M6"
    # a high score that still gets "Needs more info" because coverage is low
    assert picks["needs_more_info"]["merchant_id"] == "M9"
    # the first merchant without consent, by id
    assert picks["no_consent"]["merchant_id"] == "M11"
    assert picks["no_consent"]["score"] is None
    for case in picks.values():
        assert case["why"]


def test_the_same_queue_always_gives_the_same_picks_whatever_its_order():
    first = picker.pick(QUEUE)
    for shuffled in (list(reversed(QUEUE)), QUEUE[5:] + QUEUE[:5]):
        again = picker.pick(shuffled)
        assert {k: v["merchant_id"] for k, v in again.items()} == {
            k: v["merchant_id"] for k, v in first.items()
        }


def test_ties_are_broken_by_merchant_id():
    queue = [
        row("M7", 90, 0.65, "Strong"),
        row("M3", 90, 0.65, "Strong"),
        row("M5", 60, 0.5, "Review"),
        row("M2", 60, 0.5, "Review"),
        row("M9", 92, 0.3, "Needs more info"),
        row("M8", 92, 0.3, "Needs more info"),
        row("M1", None, None, None, consent=False),
    ]
    picks = picker.pick(queue)
    assert picks["strong"]["merchant_id"] == "M3"
    assert picks["review_low_score"]["merchant_id"] == "M2"
    assert picks["needs_more_info"]["merchant_id"] == "M8"


@pytest.mark.parametrize(
    "remove,message",
    [
        ("Strong", "No merchant in the band 'Strong'"),
        ("Review", "No merchant in the band 'Review'"),
        ("Needs more info", "No merchant in the band 'Needs more info'"),
    ],
)
def test_a_queue_without_a_case_says_which_one(remove, message):
    queue = [r for r in QUEUE if r["band"] != remove]
    with pytest.raises(picker.PickError, match=message):
        picker.pick(queue)


def test_an_empty_queue_or_one_without_a_refused_merchant_is_explained():
    with pytest.raises(picker.PickError, match="no scored merchant"):
        picker.pick([])
    with pytest.raises(picker.PickError, match="Every merchant"):
        picker.pick([r for r in QUEUE if r["consent_valid"]])


def test_a_merchant_without_a_consent_is_never_picked_for_a_score():
    for key in ("strong", "review_low_score", "needs_more_info"):
        assert picker.pick(QUEUE)[key]["consent_valid"] is True


def test_more_lists_the_next_merchants_that_fit_each_case_in_order():
    picks = picker.pick(QUEUE, more=2)
    assert picks["strong"]["also_fits"] == ["M2", "M1"]  # the nearest scores to the median
    assert picks["review_low_score"]["also_fits"] == ["M5", "M7"]  # next lowest scores
    assert picks["needs_more_info"]["also_fits"] == ["M8", "M10"]  # next highest scores
    assert picks["no_consent"]["also_fits"] == ["M12"]  # only one more exists
    assert all("also_fits" not in case for case in picker.pick(QUEUE).values())
    # the pick itself does not change when more are asked for
    assert [c["merchant_id"] for c in picks.values()] == ["M3", "M6", "M9", "M11"]


# --- the command, against a stand-in API --------------------------------------------------


class FakeApi:
    def __init__(self, queue, status=200):
        self.queue = queue
        self.status = status  # what GET /merchants answers
        self.seen: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                outer.seen.append({"path": self.path, "headers": dict(self.headers)})
                if self.path == "/merchants" and outer.status != 200:
                    body, status = {"detail": {"code": "unknown_token"}}, outer.status
                elif self.path == "/merchants":
                    body, status = outer.queue, 200
                elif self.path.endswith("/score"):
                    body = {
                        "reasons_positive": [{"sentence_en": "Payments are on time."}],
                        "reasons_negative": [{"sentence_en": "Returns are higher."}],
                    }
                    status = 200
                else:
                    body, status = {"detail": "nope"}, 404
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture()
def api():
    fake = FakeApi(QUEUE)
    yield fake
    fake.stop()


def test_the_command_prints_the_four_cases_and_reads_only_the_queue(api, capsys):
    assert picker.main(["--url", api.url]) == 0
    out = capsys.readouterr().out
    for label in ("1. STRONG", "2. REVIEW", "3. NEEDS MORE INFO", "4. NO CONSENT"):
        assert label in out
    for merchant_id in ("M3", "M6", "M9", "M11"):
        assert f"open: /merchants/{merchant_id}" in out
    assert "LOW-SCORE WARNING" not in out.split("2. REVIEW")[0]  # only on the Review case
    assert [call["path"] for call in api.seen] == ["/merchants"]  # no score card was read
    assert api.seen[0]["headers"]["X-Demo-Token"] == "viewer-1"


def test_the_command_prints_the_other_candidates(api, capsys):
    assert picker.main(["--url", api.url, "--more", "2"]) == 0
    assert "also fits: M2, M1" in capsys.readouterr().out


def test_details_reads_a_score_card_only_for_merchants_with_a_consent(api, capsys):
    assert picker.main(["--url", api.url, "--details"]) == 0
    out = capsys.readouterr().out
    paths = [call["path"] for call in api.seen]
    assert paths == [
        "/merchants",
        "/merchants/M3/score",
        "/merchants/M6/score",
        "/merchants/M9/score",
    ]
    assert "helps: Payments are on time." in out and "holds back: Returns are higher." in out


def test_json_output_can_be_read_by_another_program(api, capsys):
    assert picker.main(["--url", api.url, "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["strong"]["merchant_id"] == "M3" and data["no_consent"]["consent_valid"] is False


def test_the_site_password_comes_from_the_environment_never_the_command(api, monkeypatch, capsys):
    monkeypatch.setenv("SITE_LOGIN", "demo:secret-word")
    assert picker.main(["--url", api.url, "--basic-auth-env", "SITE_LOGIN"]) == 0
    sent = api.seen[0]["headers"]["Authorization"]
    assert base64.b64decode(sent.split()[1]).decode() == "demo:secret-word"
    assert "secret-word" not in capsys.readouterr().out
    # there is no option that takes the password itself, so it cannot end up in a shell history
    for option in ("--password", "--basic-auth"):
        with pytest.raises(SystemExit):
            picker.main(["--url", api.url, option, "demo:secret-word"])


def test_an_unreachable_api_is_a_clear_message_and_exit_code_1(api, capsys):
    api.stop()
    assert picker.main(["--url", api.url]) == 1
    out = capsys.readouterr().out
    assert "NOT PICKED" in out and "Cannot reach the API" in out and "python tasks.py api" in out


def test_an_api_that_refuses_is_reported_with_its_status():
    fake = FakeApi(QUEUE, status=401)
    try:
        with pytest.raises(picker.PickError, match="/merchants answered 401"):
            picker.api_get(fake.url, "/merchants", "nobody")
        assert picker.main(["--url", fake.url]) == 1
    finally:
        fake.stop()


def test_the_script_never_asks_for_a_decision_or_changes_anything():
    source = open(picker.__file__, encoding="utf-8").read()
    assert "method=" not in source and "POST" not in source and "data=" not in source

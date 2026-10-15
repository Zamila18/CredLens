"""Tests for the task runner (tasks.py): which commands each task runs.

No command is really run: `run_in_venv` is replaced by a recorder.
"""

from __future__ import annotations

import tasks


def _record(monkeypatch, codes=None):
    calls = []

    def fake(args, env=None):
        calls.append(args)
        return (codes or {}).get(tuple(args), 0)

    monkeypatch.setattr(tasks, "run_in_venv", fake)
    return calls


def test_train_writes_the_model_card_after_training(monkeypatch):
    calls = _record(monkeypatch)
    assert tasks.main(["train", "--mode", "taiwan_cc"]) == 0
    assert calls == [
        ["-m", "src.model.train", "--mode", "taiwan_cc"],
        ["-m", "src.model.model_card", "--mode", "taiwan_cc"],
    ]


def test_no_card_is_written_when_training_fails(monkeypatch):
    calls = _record(monkeypatch, {("-m", "src.model.train"): 1})
    assert tasks.main(["train"]) == 1
    assert calls == [["-m", "src.model.train"]]


def test_train_all_modes_writes_every_card_and_a_missing_mode_is_no_error(monkeypatch):
    missing = {("-m", "src.model.model_card", "--all-modes"): tasks.DATA_MISSING}
    calls = _record(monkeypatch, missing)
    assert tasks.main(["train", "--all-modes"]) == 0
    assert calls[-1] == ["-m", "src.model.model_card", "--all-modes"]


def test_the_data_reset_goes_through_the_guarded_loader(monkeypatch):
    calls = _record(monkeypatch)
    tasks.main(["data", "--reset-db"])
    # Only --reset: the loader refuses a shared database unless asked by name.
    assert calls[-1] == ["-m", "src.db.load", "--reset"]

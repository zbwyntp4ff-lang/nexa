from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.hexa45.prepare_sft import load_dataset, prepare_dataset


def _sample(user: str, answer: str) -> dict:
    return {"messages": [
        {"role": "user", "content": user},
        {"role": "assistant", "content": answer},
    ]}


def test_prepare_dataset_deduplicates_and_splits(tmp_path: Path):
    source = tmp_path / "raw.jsonl"
    source.write_text(
        "\n".join(json.dumps(item) for item in [
            _sample("Вопрос 1", "Ответ 1"),
            _sample("Вопрос 1", "Ответ 1"),
            _sample("Вопрос 2", "Ответ 2"),
            _sample("Вопрос 3", "Ответ 3"),
        ]) + "\n",
        encoding="utf-8",
    )

    output = tmp_path / "prepared"
    manifest = prepare_dataset(source, output, validation_ratio=0.25, seed=7)

    assert manifest["unique_samples"] == 3
    assert manifest["train_samples"] == 2
    assert manifest["validation_samples"] == 1
    assert (output / "manifest.json").exists()
    assert len((output / "train.jsonl").read_text(encoding="utf-8").splitlines()) == 2
    assert len((output / "validation.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_load_dataset_rejects_tool_role(tmp_path: Path):
    source = tmp_path / "raw.jsonl"
    source.write_text(
        json.dumps({"messages": [
            {"role": "user", "content": "x"},
            {"role": "tool", "content": "y"},
            {"role": "assistant", "content": "z"},
        ]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unsupported role"):
        load_dataset(source)


def test_load_dataset_rejects_assistant_not_last(tmp_path: Path):
    source = tmp_path / "raw.jsonl"
    source.write_text(
        json.dumps({"messages": [
            {"role": "user", "content": "x"},
            {"role": "assistant", "content": "y"},
            {"role": "user", "content": "z"},
        ]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="final message"):
        load_dataset(source)


def test_prepare_dataset_rejects_invalid_ratio(tmp_path: Path):
    source = tmp_path / "raw.jsonl"
    source.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="validation_ratio"):
        prepare_dataset(source, tmp_path / "out", validation_ratio=0.5)

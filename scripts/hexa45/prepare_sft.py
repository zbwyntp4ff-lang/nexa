"""Validate and split HEXA 4.5 supervised fine-tuning data.

Input JSONL format:
{"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}

Only system/user/assistant text messages are accepted. The script does not
download data, call external services, or print dataset contents.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any

_ALLOWED_ROLES = {"system", "user", "assistant"}


def _validate_record(record: Any, line_number: int) -> dict[str, list[dict[str, str]]]:
    if not isinstance(record, dict) or not isinstance(record.get("messages"), list):
        raise ValueError(f"line {line_number}: expected an object with a messages array")

    messages: list[dict[str, str]] = []
    for index, message in enumerate(record["messages"]):
        if not isinstance(message, dict):
            raise ValueError(f"line {line_number}: message {index} must be an object")
        role = message.get("role")
        content = message.get("content")
        if role not in _ALLOWED_ROLES:
            raise ValueError(f"line {line_number}: unsupported role at message {index}")
        if not isinstance(content, str) or not content.strip():
            raise ValueError(f"line {line_number}: empty or non-text content at message {index}")
        messages.append({"role": role, "content": content.strip()})

    roles = [message["role"] for message in messages]
    if roles.count("user") == 0 or roles.count("assistant") == 0:
        raise ValueError(f"line {line_number}: each sample needs user and assistant messages")
    if roles[-1] != "assistant":
        raise ValueError(f"line {line_number}: final message must be from assistant")
    if any(len(message["content"]) > 32_000 for message in messages):
        raise ValueError(f"line {line_number}: message exceeds 32000 characters")

    return {"messages": messages}


def load_dataset(path: Path) -> tuple[list[dict[str, Any]], str]:
    digest = hashlib.sha256()
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    with path.open("rb") as raw_file:
        for line_number, raw_line in enumerate(raw_file, start=1):
            digest.update(raw_line)
            if not raw_line.strip():
                continue
            try:
                decoded = raw_line.decode("utf-8")
                parsed = json.loads(decoded)
                record = _validate_record(parsed, line_number)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"Invalid dataset at line {line_number}: {exc}") from exc

            canonical = json.dumps(record, ensure_ascii=False, sort_keys=True)
            fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if fingerprint not in seen:
                seen.add(fingerprint)
                records.append(record)

    if len(records) < 2:
        raise ValueError("Dataset must contain at least two unique valid samples")
    return records, digest.hexdigest()


def prepare_dataset(
    input_path: Path,
    output_dir: Path,
    validation_ratio: float = 0.02,
    seed: int = 42,
) -> dict[str, Any]:
    if not 0.0 < validation_ratio < 0.5:
        raise ValueError("validation_ratio must be greater than 0 and less than 0.5")

    records, source_sha256 = load_dataset(input_path)
    shuffled = list(records)
    random.Random(seed).shuffle(shuffled)

    validation_count = max(1, round(len(shuffled) * validation_ratio))
    validation = shuffled[:validation_count]
    train = shuffled[validation_count:]
    if not train:
        raise ValueError("Not enough samples to create a training split")

    output_dir.mkdir(parents=True, exist_ok=True)
    for name, subset in (("train.jsonl", train), ("validation.jsonl", validation)):
        target = output_dir / name
        with target.open("w", encoding="utf-8", newline="\n") as file:
            for record in subset:
                file.write(json.dumps(record, ensure_ascii=False) + "\n")

    manifest = {
        "format": "hexa-sft-chat-v1",
        "source_file": input_path.name,
        "source_sha256": source_sha256,
        "unique_samples": len(records),
        "train_samples": len(train),
        "validation_samples": len(validation),
        "validation_ratio_requested": validation_ratio,
        "seed": seed,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Source JSONL file")
    parser.add_argument("--output-dir", required=True, type=Path, help="Output directory")
    parser.add_argument("--validation-ratio", type=float, default=0.02)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    manifest = prepare_dataset(
        args.input,
        args.output_dir,
        validation_ratio=args.validation_ratio,
        seed=args.seed,
    )
    print(
        "Prepared HEXA SFT dataset: "
        f"{manifest['train_samples']} train / "
        f"{manifest['validation_samples']} validation samples "
        f"({manifest['unique_samples']} unique total)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

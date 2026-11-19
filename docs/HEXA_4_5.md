# HEXA 4.5 — base model and SFT data preparation

## Current model baseline

The first reproducible baseline is Qwen3-4B with an HEXA system prompt and
serving profile. The upstream Hugging Face model card declares Apache-2.0:
https://huggingface.co/Qwen/Qwen3-4B

This is **not** an independently pretrained HEXA foundation model and the
prompt file does not change the underlying weights. It gives the project a
repeatable baseline that can later be evaluated and fine-tuned. Preserve the
upstream model attribution and license when redistributing.

## Build the Ollama model

Install Ollama on the inference host, then from the repository root run:

```bash
ollama pull qwen3:4b
ollama create hexa-4.5 -f models/hexa45/Modelfile
ollama run hexa-4.5
```

Configure NEXA:

```dotenv
AI_PROVIDER=hexa
HEXA_MODEL_URL=http://127.0.0.1:11434
HEXA_MODEL_NAME=hexa-4.5
REQUEST_TIMEOUT_SECONDS=120
```

Keep the inference port private. For a remote deployment, use a private
network or authenticated HTTPS reverse proxy. Do not expose Ollama directly
to the public internet.

## Preparing future supervised fine-tuning data

Use JSONL, one conversation per line:

```json
{"messages":[{"role":"user","content":"Привет"},{"role":"assistant","content":"Здравствуйте! Чем помочь?"}]}
```

Validate, deduplicate, and split a dataset:

```bash
python scripts/hexa45/prepare_sft.py \
  --input data/hexa45/raw.jsonl \
  --output-dir data/hexa45/prepared \
  --validation-ratio 0.02 \
  --seed 42
```

The script accepts only text messages with system/user/assistant roles,
requires at least one user and assistant message, requires the assistant to
speak last, rejects empty or oversized messages, removes exact duplicate
samples, and writes train/validation JSONL plus a source-hash manifest.

Do not place private conversations, credentials, personal data, copyrighted
corpora without appropriate rights, or unreviewed web scrapes into training
data. Review provenance, consent, license, and quality before training.

## Next milestone

1. Add a curated, licensed Russian/English dataset.
2. Establish baseline evaluation tasks and expected answers.
3. Run baseline tests against the unmodified Qwen3-4B.
4. Fine-tune only after the dataset and evaluation set are reviewed.
5. Compare the fine-tuned checkpoint against the baseline and retain it only
   if it improves measured quality without regressions.

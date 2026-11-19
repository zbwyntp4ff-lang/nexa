# HEXA 4.5 — knowledge and reasoning architecture

HEXA is being built as a model-backed assistant platform, not as a claim that
one small checkpoint contains every fact. Knowledge retrieval, calculation,
code execution, model reasoning, and evaluation are separate capabilities.

## Existing NEXA components we reuse

- Knowledge Base: document ingestion, chunking, indexing, scoped retrieval,
  citations, and prompt-injection framing.
- Research: web search and page fetching through the existing guarded pipeline.
- Calculator: AST-whitelisted arithmetic (no Python `eval`).
- Learning/evaluation: feedback snapshots and reviewable improvement proposals.

## Semantic retrieval upgrade

The Knowledge Base previously used a deterministic hashing-trick embedding.
That remains the zero-cost, offline default. For stronger semantic retrieval,
an optional Ollama embedding provider is now available.

On a private inference host:

```bash
ollama pull nomic-embed-text
```

Configure:

```dotenv
KNOWLEDGE_EMBEDDING_PROVIDER=ollama
KNOWLEDGE_EMBEDDING_BASE_URL=http://127.0.0.1:11434
KNOWLEDGE_EMBEDDING_MODEL=nomic-embed-text
KNOWLEDGE_EMBEDDING_TIMEOUT_SECONDS=20
```

The provider batches inputs, validates the response shape, rejects zero,
non-finite, or inconsistent vectors, and normalizes vectors before storage.
The Ollama endpoint must remain private or behind authenticated transport.

**Index migration:** embeddings from different providers/models are not
interchangeable. When changing embedding provider or model, back up and
rebuild the vector index by re-ingesting the source documents. Do not mix old
and new vectors in one index. The default remains `local`, so existing
installations do not change behavior until explicitly configured.

## Knowledge domains to curate

Build a reviewed, licensed corpus in independently versioned collections:

1. School curriculum: mathematics, physics, chemistry, biology, informatics,
   history, geography, literature, and civics.
2. University mathematics: calculus, linear algebra, differential equations,
   probability, statistics, numerical methods, and optimization.
3. Physics: classical mechanics, electromagnetism, thermodynamics, optics,
   relativity, quantum mechanics, and experimental methods.
4. Engineering: electrical and electronic engineering, mechanical design,
   materials, control systems, robotics, CAD/CAE references, and safety.
5. Computer science: algorithms, data structures, operating systems,
   networking, databases, compilers, distributed systems, and cybersecurity.
6. Human and world knowledge: anatomy and physiology, psychology, ecology,
   economics, law, and history, with source dates and domain-specific cautions.

Every source record should carry title, author/publisher, URL or stable
identifier, publication/version date, language, license, collection, and
review status. Prefer public-domain, openly licensed, official, and
institutional sources. Do not bulk-copy copyrighted textbooks or private
user material without permission.

## Math and code capability layers

- Math: retain the safe arithmetic tool; add a separately sandboxed symbolic
  and numerical computation service (e.g. SymPy/SciPy) with time, memory, and
  expression-size limits. Do not execute arbitrary model-generated Python in
  the API process.
- Code: use an isolated container or remote runner with no ambient secrets,
  restricted network, CPU/memory/time quotas, and explicit user approval for
  filesystem or external side effects.
- Engineering: connect validated calculators and domain simulators only
  after test fixtures and unit-aware input/output validation exist.

## Evaluation before claims

Create held-out tests by domain, record expected answers and accepted
tolerances, and score factual accuracy, citation correctness, calculation
accuracy, code test pass rate, and calibration. Keep training data separate
from evaluation data. Do not describe HEXA as expert-level until measured
benchmarks support that claim.

## Milestones

1. Semantic embeddings and retrieval reliability.
2. Source metadata, collection taxonomy, ingestion review, and re-indexing.
3. Math computation service and deterministic tests.
4. Sandboxed code runner and repository-level coding evaluations.
5. Curated domain corpus and held-out benchmarks.
6. Fine-tuning experiments only after data rights and baseline metrics are
   reviewed.

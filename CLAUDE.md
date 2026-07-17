# generate-image-skill

A public Agent Skill + self-contained CLI that generates images locally with
FLUX.1-schnell (via mflux) on Apple Silicon. See `README.md` for the product
overview and `SKILL.md` for the agent-facing instructions.

## Commands

- **Run the test suite** (no model needed, ~0.1s): `uvx --with pillow pytest tests/ -v`
- **Environment check** (pure stdlib, runs on system python3): `python3 scripts/doctor.py`
- **Generate an image**: `uv run scripts/generate.py "PROMPT" --out out.webp --size 1440x800`
- **Dry-run** (validate everything without loading the model): add `--dry-run`

## Architecture

- `scripts/imagegen_core.py` — all pure logic (size planning, format-aware
  saving, style-config discovery, manifest parsing). No mflux import — fully
  unit-testable. Imports Pillow.
- `scripts/generate.py` — the CLI. PEP 723 inline deps (`mflux==0.18.0`). Dispatches
  to a backend; `--dry-run` never loads mflux.
- `scripts/backends.py` — generation backends behind one `generate(...)` interface:
  `LocalBackend` (mflux, lazy-imported) and `ReplicateBackend` (hosted, stdlib
  `urllib`). Pure helpers (`nearest_aspect_ratio`, `replicate_payload`,
  `parse_replicate_output`) are unit-tested; the live hosted HTTP path is not.
- `scripts/keychain.py` — macOS Keychain storage for hosted API keys via the
  `security` tool. The agent never handles raw keys: user stores once, CLI reads
  at run time. Stdlib only.
- `scripts/doctor.py` — preflight environment check. **Pure standard library,
  targets Python 3.9+** (the stock macOS `python3`) so it runs before uv exists.
  Do not add third-party imports or 3.10+ syntax here.
- `tests/` — pytest, runs without mflux.
- `SKILL.md` + `reference/prompting.md` — agent-facing docs.

## Conventions

- **Errors that reach the user must be actionable** (`error: ...`), never raw
  tracebacks. Core functions raise `ValueError`; the CLI catches and formats.
- **Validate before side effects** (e.g. reject a bad extension before mkdir or
  before loading the model).
- mflux's Python API path has changed across versions — when bumping the pin,
  re-verify against the installed package and re-run a live generation.

## Context

Design spec and implementation plan live in `docs/superpowers/`. Cross-session
history is in `.agents/sessions/`.

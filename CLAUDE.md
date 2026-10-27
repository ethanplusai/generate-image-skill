# generate-image-skill

A public Agent Skill + self-contained CLI that generates images for coding
agents: through Codex's built-in image tool on the user's ChatGPT plan (default
when signed in), locally with FLUX.1-schnell (via mflux) on Apple Silicon, or a
hosted API. See `README.md` for the product
overview and `SKILL.md` for the agent-facing instructions.

## Commands

- **Run the test suite** (no model needed, ~0.1s): `uvx --with "pillow<13" pytest tests/ -v`
- **Environment check** (pure stdlib, runs on system python3): `python3 scripts/doctor.py`
- **Generate an image**: `uv run scripts/generate.py "PROMPT" --out out.webp --size 1440x800`
- **Dry-run** (validate everything without loading the model): add `--dry-run`

## Architecture

- `scripts/imagegen_core.py` — all pure logic (size planning, format-aware
  saving, style-config discovery, manifest parsing). No mflux import — fully
  unit-testable. Imports Pillow.
- `scripts/generate.py` — the CLI. PEP 723 inline deps are Pillow only (pinned
  `<13`: Pillow 13 breaks on Python 3.12). `mflux==0.18.0` is added on demand by
  `ensure_mflux()`, which re-execs under `uv run --with` the first time the local
  backend is used. `--backend auto` resolves to codex (if `codex login` is
  ChatGPT) else local. `--dry-run` never loads mflux.
- `scripts/backends.py` — generation backends behind one `generate(...)` interface:
  `CodexBackend` (runs `codex exec --json` headless, collects the image from
  `$CODEX_HOME/generated_images/<thread-id>/`), `LocalBackend` (mflux,
  lazy-imported) and hosted backends `ReplicateBackend`,
  `OpenAIBackend`, and `GeminiBackend` (stdlib `urllib`). Providers are registered in the
  `HOSTED_BACKENDS` map — add a class + one entry to add a provider. Pure helpers
  (payload builders, response parsers, size selection) are unit-tested; the live
  hosted HTTP paths are not (they bill real accounts). The live codex path is
  not unit-tested either (uses plan quota); verify it by hand after changes.
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

#!/usr/bin/env python3
"""Preflight environment check for generate-image-skill.

Pure standard library — no third-party imports — so it runs on a bare macOS
with plain `python3`, BEFORE uv or anything else is installed:

    python3 scripts/doctor.py

It checks every prerequisite for local image generation and prints a
copy-pasteable fix for whatever is missing. Exit code 0 means "ready to
generate"; exit code 1 means a hard blocker needs fixing first.

Must stay compatible with the stock macOS `python3` (3.9), so this file
targets 3.9+ and avoids any newer-only syntax at runtime.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

MIN_FREE_BYTES = 8 * 1024**3  # model is ~7 GB; leave headroom
RECOMMENDED_RAM_BYTES = 24 * 1024**3
MIN_RAM_BYTES = 16 * 1024**3
MODEL_CACHE_DIRNAME = "models--dhairyashil--FLUX.1-schnell-mflux-4bit"

OK = "ok"
WARN = "warn"
FAIL = "fail"

_ICON = {OK: "✓", WARN: "!", FAIL: "✗"}


def check_platform(system: str, machine: str) -> tuple[str, str, str | None]:
    if system == "Darwin" and machine == "arm64":
        return OK, "Apple Silicon Mac", None
    return (
        FAIL,
        f"unsupported platform ({system}/{machine})",
        "generate-image-skill v1 needs an Apple Silicon Mac (M1 or newer). "
        "Linux/CUDA support is on the roadmap.",
    )


def check_python(version: tuple[int, int]) -> tuple[str, str, str | None]:
    if version >= (3, 11):
        return OK, f"Python {version[0]}.{version[1]}", None
    return (
        WARN,
        f"Python {version[0]}.{version[1]} (this interpreter)",
        "uv supplies its own Python for generation, so this is usually fine. "
        "3.11+ is only needed to run the test suite directly.",
    )


def check_uv(uv_path: str | None) -> tuple[str, str, str | None]:
    if uv_path:
        return OK, f"uv ({uv_path})", None
    return (
        FAIL,
        "uv is not installed",
        "Install it, then re-run this check:\n"
        "      brew install uv\n"
        "    or, without Homebrew:\n"
        "      curl -LsSf https://astral.sh/uv/install.sh | sh\n"
        "    uv runs the generator and manages every Python dependency for you.",
    )


def check_disk(free_bytes: int) -> tuple[str, str, str | None]:
    gb = free_bytes / 1024**3
    if free_bytes >= MIN_FREE_BYTES:
        return OK, f"{gb:.0f} GB free disk", None
    return (
        FAIL,
        f"only {gb:.1f} GB free disk",
        "The model download needs ~7 GB. Free up some space before the first run.",
    )


def check_ram(total_bytes: int) -> tuple[str, str, str | None]:
    gb = total_bytes / 1024**3
    if total_bytes >= RECOMMENDED_RAM_BYTES:
        return OK, f"{gb:.0f} GB RAM", None
    if total_bytes >= MIN_RAM_BYTES:
        return (
            WARN,
            f"{gb:.0f} GB RAM",
            "16 GB works, but generation may swap. 24 GB+ is noticeably smoother.",
        )
    return (
        WARN,
        f"{gb:.0f} GB RAM",
        "Under 16 GB: generation will be slow and swap heavily, but should still run.",
    )


def check_model_cache(cached: bool) -> tuple[str, str, str | None]:
    if cached:
        return OK, "model already downloaded", None
    return (
        WARN,
        "model not downloaded yet",
        "The first generation downloads ~7 GB from Hugging Face "
        "(one time, no account needed).",
    )


def overall_status(statuses: list[str]) -> str:
    if FAIL in statuses:
        return FAIL
    if WARN in statuses:
        return WARN
    return OK


def format_report(findings: list[tuple[str, str, str, str | None]]) -> str:
    """Render findings as a report. Each finding is (label, status, detail, fix)."""
    lines = ["generate-image-skill — environment check", ""]
    for label, status, detail, fix in findings:
        lines.append(f"  {_ICON[status]} {label}: {detail}")
        if fix:
            for fix_line in fix.split("\n"):
                lines.append(f"      {fix_line}")
    lines.append("")
    status = overall_status([s for _, s, _, _ in findings])
    if status == FAIL:
        lines.append("Not ready yet — fix the ✗ item(s) above, then re-run this check.")
    elif status == WARN:
        lines.append("Ready to generate. The ! notes above are advisory, not blockers.")
    else:
        lines.append("All set — you're ready to generate images.")
    return "\n".join(lines)


def _total_ram_bytes() -> int | None:
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True,
            text=True,
            check=True,
        )
        return int(result.stdout.strip())
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None


def _free_disk_bytes() -> int | None:
    try:
        return shutil.disk_usage(Path.home()).free
    except OSError:
        return None


def _model_cached() -> bool:
    hf_home = os.environ.get("HF_HOME")
    roots = []
    if hf_home:
        roots.append(Path(hf_home) / "hub")
    roots.append(Path.home() / ".cache" / "huggingface" / "hub")
    return any((root / MODEL_CACHE_DIRNAME).is_dir() for root in roots)


def gather_findings() -> list[tuple[str, str, str, str | None]]:
    findings = []

    status, detail, fix = check_platform(platform.system(), platform.machine())
    findings.append(("platform", status, detail, fix))

    status, detail, fix = check_python(sys.version_info[:2])
    findings.append(("python", status, detail, fix))

    status, detail, fix = check_uv(shutil.which("uv"))
    findings.append(("uv", status, detail, fix))

    free = _free_disk_bytes()
    if free is not None:
        status, detail, fix = check_disk(free)
        findings.append(("disk", status, detail, fix))

    ram = _total_ram_bytes()
    if ram is not None:
        status, detail, fix = check_ram(ram)
        findings.append(("memory", status, detail, fix))

    status, detail, fix = check_model_cache(_model_cached())
    findings.append(("model", status, detail, fix))

    return findings


def main() -> int:
    findings = gather_findings()
    print(format_report(findings))
    return 1 if overall_status([s for _, s, _, _ in findings]) == FAIL else 0


if __name__ == "__main__":
    sys.exit(main())

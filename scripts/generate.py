#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["mflux==0.18.0"]
# ///
"""Generate images locally with FLUX.1-schnell for website/app assets.

Single image:
    uv run scripts/generate.py "warm photo of a pottery studio" \
        --out public/hero.webp --size 1440x800

Batch (loads the model once for all jobs):
    uv run scripts/generate.py --batch manifest.json
"""

import argparse
import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import keychain
from backends import HOSTED_PROVIDERS, get_backend
from imagegen_core import (
    SUPPORTED_EXTENSIONS,
    Job,
    apply_style,
    discover_style_config,
    finalize_image,
    numbered_outputs,
    parse_manifest,
    parse_size,
    plan_generation_size,
    resolve_seeds,
    save_image,
)

DEFAULT_MODEL = "dhairyashil/FLUX.1-schnell-mflux-4bit"
BASE_MODEL = "schnell"


def check_environment(backend: str) -> None:
    # Hosted backends offload compute, so they don't need Apple Silicon — but
    # keys live in the macOS Keychain, so they still require macOS in v1.
    if backend != "local":
        if sys.platform != "darwin":
            sys.exit(
                "hosted backends currently require macOS "
                "(API keys are stored in the Keychain)."
            )
        return
    if sys.platform != "darwin" or platform.machine() != "arm64":
        sys.exit(
            "the local backend requires an Apple Silicon Mac (macOS arm64).\n"
            "On another machine, use a hosted backend (e.g. --backend replicate).\n"
            "Linux/CUDA support is on the roadmap:\n"
            "https://github.com/ethanplusai/generate-image-skill#roadmap"
        )
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, check=True
        )
        if int(result.stdout.strip()) < 16 * 1024**3:
            print(
                "warning: under 16 GB RAM; generation may be very slow (swapping).",
                file=sys.stderr,
            )
    except (OSError, subprocess.CalledProcessError, ValueError):
        pass  # RAM check is best-effort only


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate images locally with FLUX.1-schnell."
    )
    parser.add_argument("prompt", nargs="?", help="image description")
    parser.add_argument("--out", help="output path (.webp, .png, or .jpg)")
    parser.add_argument("--size", help="exact output size, e.g. 1440x800")
    parser.add_argument("--seed", type=int, help="fixed seed for reproducibility")
    parser.add_argument(
        "--count", type=int, default=1, help="number of candidates (hero-1.webp, ...)"
    )
    parser.add_argument("--steps", type=int, default=4, help="inference steps")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="HF model repo")
    parser.add_argument(
        "--batch", help="JSON manifest: [{prompt, out, size, seed?, count?}, ...]"
    )
    parser.add_argument(
        "--no-style", action="store_true", help="ignore project imagegen.toml"
    )
    parser.add_argument(
        "--backend",
        choices=("local", *HOSTED_PROVIDERS),
        default="local",
        help="generation backend (default: local mflux; hosted needs a stored key)",
    )
    parser.add_argument(
        "--set-key",
        metavar="PROVIDER",
        help="store a hosted provider's API key in the macOS Keychain, then exit",
    )
    parser.add_argument(
        "--delete-key",
        metavar="PROVIDER",
        help="remove a provider's stored API key, then exit",
    )
    parser.add_argument(
        "--list-keys",
        action="store_true",
        help="show which hosted providers have a stored key, then exit",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="open each result in the default image viewer after saving (macOS)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the generation plan without loading the model",
    )
    return parser


def handle_key_commands(args) -> bool:
    """Run any key-management command. Returns True if one ran (caller exits)."""
    if args.set_key:
        import getpass

        if not sys.stdin.isatty():
            sys.exit(
                "error: --set-key must be run interactively in a terminal so the "
                "key is typed at a hidden prompt.\nRun it yourself in a shell; do "
                "not invoke it from an agent or a pipe."
            )
        key = getpass.getpass(
            f"Paste the API key for '{args.set_key}' (input hidden): "
        ).strip()
        if not key:
            sys.exit("error: no key entered")
        try:
            keychain.set_key(args.set_key, key)
        except RuntimeError as exc:
            sys.exit(f"error: {exc}")
        print(f"stored key for '{args.set_key}' in the macOS Keychain.")
        return True
    if args.delete_key:
        deleted = keychain.delete_key(args.delete_key)
        print(
            f"removed stored key for '{args.delete_key}'."
            if deleted
            else f"no key was stored for '{args.delete_key}'."
        )
        return True
    if args.list_keys:
        for provider in HOSTED_PROVIDERS:
            mark = "stored" if keychain.key_exists(provider) else "not set"
            print(f"  {provider}: {mark}")
        return True
    return False


def main() -> None:
    args = build_parser().parse_args()

    if handle_key_commands(args):
        return

    if args.count < 1:
        sys.exit("error: --count must be at least 1")
    if args.steps < 1:
        sys.exit("error: --steps must be at least 1")
    if args.seed is not None and args.seed < 0:
        sys.exit("error: --seed must be non-negative")

    try:
        if args.batch:
            if args.prompt or args.out or args.size or args.seed is not None or args.count != 1:
                print(
                    "warning: --batch ignores prompt, --out, --size, --seed, and --count",
                    file=sys.stderr,
                )
            batch_path = Path(args.batch)
            if not batch_path.is_file():
                sys.exit(f"error: manifest not found: {batch_path}")
            jobs = parse_manifest(batch_path)
        elif args.prompt:
            if not args.out or not args.size:
                sys.exit("error: --out and --size are required with a prompt")
            width, height = parse_size(args.size)
            jobs = [
                Job(
                    prompt=args.prompt,
                    out=Path(args.out),
                    width=width,
                    height=height,
                    seed=args.seed,
                    count=args.count,
                )
            ]
        else:
            sys.exit("error: provide a prompt or --batch manifest.json")

        for job in jobs:
            if job.out.suffix.lower() not in SUPPORTED_EXTENSIONS:
                raise ValueError(
                    f"unsupported output format {job.out.suffix!r} for {job.out}: "
                    "use .webp, .png, or .jpg"
                )

        style = None if args.no_style else discover_style_config(Path.cwd())
    except (ValueError, OSError) as exc:
        sys.exit(f"error: {exc}")
    plans = []
    for job in jobs:
        job.prompt = apply_style(job.prompt, style)
        gen_w, gen_h, needs_upscale = plan_generation_size(job.width, job.height)
        outs = numbered_outputs(job.out, job.count)
        seeds = resolve_seeds(job.seed, job.count)
        plans.append((job, gen_w, gen_h, needs_upscale, outs, seeds))

    if args.dry_run:
        for job, gen_w, gen_h, needs_upscale, outs, seeds in plans:
            note = " (will be Lanczos-upscaled)" if needs_upscale else ""
            for out, seed in zip(outs, seeds):
                print(
                    f"[dry-run] {out}  {job.width}x{job.height}  "
                    f"gen@{gen_w}x{gen_h}{note}  seed={seed}"
                )
                print(f"          prompt: {job.prompt}")
        return

    check_environment(args.backend)
    try:
        api_key = (
            keychain.get_key(args.backend)
            if args.backend in HOSTED_PROVIDERS
            else None
        )
        backend = get_backend(
            args.backend,
            model=args.model,
            base_model=BASE_MODEL,
            api_key=api_key,
        )
    except ValueError as exc:
        sys.exit(f"error: {exc}")
    run_plans(plans, backend=backend, steps=args.steps, open_after=args.open)


def open_in_viewer(path: Path) -> None:
    """Open a saved image in the Mac's default viewer. Best-effort."""
    try:
        subprocess.run(["open", str(path)], check=False)
    except OSError:
        pass


def run_plans(plans, backend, steps: int, open_after: bool = False) -> None:
    for job, gen_w, gen_h, needs_upscale, outs, seeds in plans:
        for out, seed in zip(outs, seeds):
            try:
                raw = backend.generate(job.prompt, gen_w, gen_h, seed, steps)
            except (ValueError, OSError) as exc:
                # OSError covers urllib's URLError/HTTPError; ValueError covers
                # bad/empty provider responses. Keep it actionable, not a traceback.
                sys.exit(f"error: image generation failed: {exc}")
            if raw.width < job.width or raw.height < job.height:
                print(
                    f"warning: {out} upscaled from {raw.width}x{raw.height} "
                    f"to {job.width}x{job.height} (source was smaller).",
                    file=sys.stderr,
                )
            image = finalize_image(raw, job.width, job.height)
            save_image(image, out)
            print(f"wrote {out} ({job.width}x{job.height}, seed={seed})")
            if open_after:
                open_in_viewer(out)


if __name__ == "__main__":
    main()

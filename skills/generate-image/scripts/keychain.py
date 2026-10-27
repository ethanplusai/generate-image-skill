"""macOS Keychain storage for hosted-backend API keys.

Hosted image providers need an API key. Storing it safely — and keeping it out
of the coding agent's context — is the whole point of this module:

- The **user** runs `--set-key <provider>` once and types the secret at a
  hidden prompt. It goes into the login Keychain, encrypted at rest and
  access-controlled by macOS.
- The **generator** retrieves it at run time via `get_key`.
- The **agent** never handles the raw key: it only ever invokes the CLI, so the
  secret never lands in a prompt, a transcript, a log, or the shell history.

Pure standard library (just the `security` tool), so it has no dependencies.
"""

from __future__ import annotations

import subprocess

SERVICE_PREFIX = "generate-image-skill"


def _service(provider: str) -> str:
    return f"{SERVICE_PREFIX}:{provider}"


def set_key(provider: str, key: str) -> None:
    """Store (or replace) the API key for a provider in the login Keychain.

    On failure, raises RuntimeError with only the exit status — never the
    command or the key. (The key is passed as an argv element, so it is briefly
    visible to a local `ps` during the call; acceptable for a one-time
    interactive setup, but that is why nothing here echoes or re-raises it.)
    """
    result = subprocess.run(
        [
            "security",
            "add-generic-password",
            "-U",  # update the item if it already exists
            "-a",
            provider,
            "-s",
            _service(provider),
            "-w",
            key,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"could not store the key in the Keychain "
            f"(security exited with status {result.returncode})"
        )


def key_exists(provider: str) -> bool:
    """Check whether a key is stored without materializing the secret."""
    result = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-a",
            provider,
            "-s",
            _service(provider),
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def get_key(provider: str) -> str | None:
    """Return the stored API key for a provider, or None if none is stored."""
    result = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-a",
            provider,
            "-s",
            _service(provider),
            "-w",  # print only the password to stdout
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def delete_key(provider: str) -> bool:
    """Remove a provider's stored key. Returns True if something was deleted."""
    result = subprocess.run(
        [
            "security",
            "delete-generic-password",
            "-a",
            provider,
            "-s",
            _service(provider),
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0

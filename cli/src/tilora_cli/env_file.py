"""Line-based KEY=VALUE get/set for .env files.

Native port of deploy/install.sh's get_env_value/set_env_value (there,
inline python3 heredocs) — same semantics: get returns the last matching
line, set replaces the first match or appends if the key isn't present.
"""

from __future__ import annotations

from pathlib import Path


def get_env_value(path: Path, key: str) -> str | None:
    if not path.is_file():
        return None
    prefix = f"{key}="
    value = None
    for line in path.read_text().splitlines():
        if line.startswith(prefix):
            value = line[len(prefix) :]
    return value


def set_env_value(path: Path, key: str, value: str) -> None:
    prefix = f"{key}="
    lines = path.read_text().splitlines() if path.is_file() else []
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = prefix + value
            break
    else:
        lines.append(prefix + value)
    path.write_text("\n".join(lines) + "\n")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Windows‑friendly updater for npm & selected global CLIs.

- Checks installed (global) versions against the registry
- Updates silently by default (toggle via flags)
- Optionally updates npm first
- Suppresses "looking for funding" notices
- Prints number of changed packages
- Keeps the window open after double‑click (toggle)
- Extend via PACKAGES
- https://github.com/wbdb/npm-updater-ai-cli
"""

import json
import os
import re
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

# =============================
# Settings
# =============================
AUTO_UPDATE_NPM: bool = True         # update npm first if newer
CONFIRM_BEFORE_UPDATE: bool = False  # ask before updates/installs
PAUSE_AT_END: bool = True            # keep window open at the end

# Target packages (easy to extend)
PACKAGES = [
    ("Gemini CLI", ["@google/gemini-cli", "gemini-cli"]),
    ("OpenAI Codex CLI", ["@openai/codex", "openai"]),
]

# Disable "looking for funding" noise
os.environ.setdefault("NPM_CONFIG_FUND", "false")
os.environ.setdefault("npm_config_fund", "false")

# =============================
# npm / process helpers
# =============================

def npm_exe() -> str:
    """Resolve npm executable (Windows: npm.cmd)."""
    return shutil.which("npm") or shutil.which("npm.cmd") or "npm"


def run(cmd: List[str]) -> Tuple[int, str, str]:
    """Run a command → (rc, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            env=os.environ,
        )
        return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()
    except FileNotFoundError:
        return 127, "", f"Command not found: {cmd[0]}"


def pause_end() -> None:
    if PAUSE_AT_END:
        try:
            input("\nPress Enter to exit … ")
        except EOFError:
            pass


def ensure_npm() -> None:
    if shutil.which("npm") is None and shutil.which("npm.cmd") is None:
        print("npm not found. Please install Node.js/npm or restart the shell.")
        pause_end()
        sys.exit(2)

# =============================
# Version logic
# =============================

def get_installed_global_map() -> Dict[str, str]:
    """Return global packages as {name: version}."""
    rc, out, err = run([npm_exe(), "ls", "-g", "--depth=0", "--json"])
    if rc != 0 and err:
        print(f"Warning: could not read global package list: {err}")
        return {}
    try:
        data = json.loads(out or '{}')
    except json.JSONDecodeError:
        print("Warning: unexpected output from 'npm ls -g --json'.")
        return {}
    deps = data.get("dependencies", {}) if isinstance(data, dict) else {}
    result: Dict[str, str] = {}
    for name, info in deps.items():
        if isinstance(info, dict) and isinstance(info.get("version"), str):
            result[name] = info["version"]
    return result


def get_latest_version(pkg: str) -> Optional[str]:
    rc, out, err = run([npm_exe(), "view", pkg, "version", "--json"])
    if rc == 0 and out:
        try:
            data = json.loads(out)
            if isinstance(data, str):
                return data.strip()
            return str(data)
        except json.JSONDecodeError:
            return out.strip().strip('"')
    return None


def parse_semver(v: str) -> Tuple[int, int, int, str]:
    core, _, pre = (v or "").partition('-')
    parts = core.split('.')
    try:
        M = int(parts[0]) if len(parts) > 0 else 0
        m = int(parts[1]) if len(parts) > 1 else 0
        p = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        return (0, 0, 0, 'z')
    return (M, m, p, pre or '~')


def is_outdated(local: Optional[str], latest: Optional[str]) -> bool:
    if latest is None:
        return False
    if local is None:
        return True
    return parse_semver(local) < parse_semver(latest)

# =============================
# Update actions
# =============================

_CHANGED_RE = re.compile(r"changed\s+(\d+)\s+packages?(?:.*?in\s+([0-9.]+\w+))?", re.IGNORECASE | re.DOTALL)


def install_or_update(pkg: str) -> Tuple[bool, int, Optional[str]]:
    """Install/Update a package. Returns (success, changed_count, time_str)."""
    print("Installing/updating …")
    rc, out, err = run([npm_exe(), "install", "-g", pkg])
    if rc == 0:
        changed, t = 0, None
        if out:
            m = _CHANGED_RE.search(out)
            if m:
                try:
                    changed = int(m.group(1))
                except Exception:
                    changed = 0
                if len(m.groups()) >= 2:
                    t = m.group(2)
        print("Done.")
        if t:
            print(f"Changed packages: {changed} (in {t})")
        else:
            print(f"Changed packages: {changed}")
        return True, changed, t
    print("Update failed:")
    if err:
        print(err)
    elif out:
        print(out)
    return False, 0, None


def maybe_confirm(action: str) -> None:
    if CONFIRM_BEFORE_UPDATE:
        try:
            input(f"{action} – press Enter to confirm … ")
        except EOFError:
            pass


def update_target(display: str, candidates: List[str], installed_map: Dict[str, str]) -> None:
    print(f"\n— {display} —")

    # find installed version (any candidate)
    installed_ver: Optional[str] = None
    installed_name: Optional[str] = None
    for cand in candidates:
        if cand in installed_map:
            installed_name = cand
            installed_ver = installed_map[cand]
            break

    # determine registry candidate + latest version (first hit)
    latest_ver: Optional[str] = None
    chosen_registry_name: Optional[str] = None
    for cand in candidates:
        v = get_latest_version(cand)
        if v:
            chosen_registry_name = cand
            latest_ver = v
            break

    print(f"Current {display} version: {installed_ver if installed_ver else 'Not installed'}")
    print(f"Latest {display} version: {latest_ver if latest_ver else 'Unknown'}")

    if chosen_registry_name is None:
        print("Warning: could not resolve latest registry version. Check package name.")
        return

    if is_outdated(installed_ver, latest_ver):
        maybe_confirm("Update required")
        ok, changed, t = install_or_update(chosen_registry_name)
        if ok:
            new_map = get_installed_global_map()
            print(f"Now installed: {display} {new_map.get(chosen_registry_name, 'Unknown')}")
    else:
        print("Already up to date.")


def update_npm_if_needed() -> None:
    print("\n— npm itself —")
    rc, out, err = run([npm_exe(), "-v"])  # local npm version
    local = out.strip() if rc == 0 else None
    latest = get_latest_version("npm")
    print(f"Current npm version: {local if local else 'Unknown'}")
    print(f"Latest npm version: {latest if latest else 'Unknown'}")

    if is_outdated(local, latest):
        maybe_confirm("npm update required")
        ok, changed, t = install_or_update("npm@latest")
        if ok:
            rc2, out2, _ = run([npm_exe(), "-v"])  # re-read
            newv = out2.strip() if rc2 == 0 else 'Unknown'
            print(f"npm updated to {newv}")
    else:
        print("npm is current.")

# =============================
# Main
# =============================

def main() -> None:
    ensure_npm()

    print("\nnpm CLI Updater")
    print("This script checks global npm installations and updates when needed.")

    if AUTO_UPDATE_NPM:
        update_npm_if_needed()

    installed_map = get_installed_global_map()

    for display, candidates in PACKAGES:
        update_target(display, candidates, installed_map)

    print("\nDone")
    print("All packages were checked.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Aborted by user.")
        sys.exit(130)
    finally:
        pause_end()

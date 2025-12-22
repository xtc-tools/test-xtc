#!/usr/bin/env python3

import re
import sys
from pathlib import Path
import base64
import logging
import argparse
import subprocess
import shlex
import os

logger = logging.getLogger(__file__)

BAN_FILE = str(Path(__file__).parent / "banwords.b64")

def cmd_output(cmd: str, cwd: str) -> str:
    cmd_lst = shlex.split(cmd)
    p = subprocess.run(cmd_lst, capture_output=True, check=True, text=True, cwd=cwd)
    if p.returncode != 0:
        raise RuntimeError(
            f"executing command failed: {cmd}:\n"
            " stdout: {p.stdout}\n"
            " stderr: {p.stderr}"
    )
    return p.stdout

def get_git_paths(top_dir: str, dirs: list[str]) -> list[str]:
    out = []
    for path in dirs:
        cmd = f"git ls-files {path}"
        out += cmd_output(cmd, cwd=top_dir).splitlines()
    paths = list(dict.fromkeys(out))
    return paths

def filter_paths(
        files: list[str],
        includes: list[str],
        excludes: list[str] = [],
) -> list[str]:
    paths = [Path(p) for p in files]
    filtered = [
        str(p) for p in paths
        if any(p.match(pat) for pat in includes)
        and not any(p.match(pat) for pat in excludes)
    ]
    return filtered

def decode_banfile(fname: str) -> str:
    words = []
    return base64.b64decode(Path(fname).read_text()).decode()

def load_banlist(fname: str) -> re.Pattern:
    content = decode_banfile(fname)
    words = []
    for l in content.splitlines():
        l = l.strip()
        if l and not l.startswith("#"):
            words.append(re.escape(l))
    return re.compile(r"\b(" + "|".join(words) + r")\b", re.IGNORECASE)

def check_file(fname: str, pattern: re.Pattern, top: str = ".", show: bool = False):
    count = 0
    path = Path(top) / fname
    try:
        text = path.read_text()
    except UnicodeDecodeError as e:
        text = ""
    for idx, line in enumerate(text.splitlines()):
        matches = list(dict.fromkeys(pattern.findall(line)))
        if matches != []:
            logger.error(
                "found %d banned word\n%s:%d: %s",
                len(matches),
                path,
                idx+1,
                ", ".join(matches) if show
                else f"<hidden>",
            )
        count += len(matches)
    return count

def main():

    TOP_DIR = Path(os.path.relpath(Path(__file__).resolve().parents[2], Path.cwd()))
    DIRS = [Path(".")]

    LICENSE = TOP_DIR / "LICENSE"
    INCLUDES = ['*']
    EXCLUDES = []
    BAN_FILE = Path(__file__).parent / "banwords.b64"

    parser = argparse.ArgumentParser(
        description="Check/apply LICENSE file to sources",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--apply", action=argparse.BooleanOptionalAction, default=False,
        help="apply removal of banned words",
    )
    parser.add_argument(
        "--check", action=argparse.BooleanOptionalAction, default=True,
        help="check banned words",
    )
    parser.add_argument(
        "--ban", type=str, default=BAN_FILE,
        help="banned words base64 file",
    )
    parser.add_argument(
        "--show", action=argparse.BooleanOptionalAction, default=False,
        help="show banned words in output",
    )
    parser.add_argument(
        "--top", type=str, default=str(TOP_DIR),
        help="top level directory",
    )
    parser.add_argument(
        "--dirs", nargs="+", type=str, default=[str(d) for d in DIRS],
        help="dirs to apply",
    )
    parser.add_argument(
        "--includes", nargs="+", type=str, default=INCLUDES,
        help="includes globs patterns",
    )
    parser.add_argument(
        "--excludes", nargs="+", type=str, default=EXCLUDES,
        help="excludes globs patterns",
    )
    args=parser.parse_args()

    logging.basicConfig()
    logger.setLevel(logging.INFO)

    paths = get_git_paths(args.top, args.dirs)
    paths = filter_paths(paths, args.includes, args.excludes)
    if len(paths) == 0:
        logger.warning("No file found")
        raise SystemExit()

    pattern = load_banlist(args.ban)
    total_count = 0
    for file in paths:
        count = check_file(file, pattern, top=args.top, show=args.show)
        total_count += count

    if total_count:
        suffix = "" if args.show else ", run with --show to see actual banned words"
        logger.error(
            "found %d banned word in %d files%s", total_count, len(paths), suffix
        )
        raise SystemExit(1)
    logger.info("Checked %d files", len(paths))

if __name__ == "__main__":
    main()

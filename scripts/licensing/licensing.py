#!/usr/bin/env python3

from functools import cache
import subprocess
import shlex
from pathlib import Path
import logging
import argparse
import os

logger = logging.getLogger(__file__)

LOADER = "#!"
COMMENTS = {
    "py": "# ",
    "c": "// ",
    "h": "// ",
    "cpp": "// ",
    "hpp": "// ",
}

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

@cache
def get_license_header(license_file: str, suffix: str) -> list[str]:
    comment = COMMENTS[suffix]
    header = [
        f"{comment}{l}".rstrip()
        for l in Path(license_file).read_text().splitlines()
    ]
    return header

def apply_license(license_file: str, fname: str, top: str = ".") -> int:
    path = Path(top) / fname
    suffix = path.suffix[1:]
    header = get_license_header(license_file, suffix)
    comment = COMMENTS[suffix]
    in_lines = path.read_text().splitlines()
    if any([
            l.startswith(comment) and "Copyright" in l
            for l in in_lines
           ]):
        logger.debug(f"Assuming file already licenced: {path}")
        return 0
    out_lines = []
    if LOADER and in_lines and in_lines[0].startswith(LOADER):
        out_lines += in_lines[0]
        in_lines = in_lines[1:]
    out_lines += header
    out_lines += in_lines
    tmp_path = Path(f"{path}.tmp")
    with open(tmp_path, "w") as outf:
        for l in out_lines:
            outf.write(l)
    tmp_path.replace(path)
    return 1

def check_license(license_file: str, fname: str, top: str = ".") -> bool:
    path = Path(top) / fname
    suffix = path.suffix[1:]
    header = get_license_header(license_file, suffix)
    in_lines = path.read_text().splitlines()
    start = 1
    if LOADER and in_lines and in_lines[0].startswith(LOADER):
        in_lines = in_lines[1:]
        start = 2
    for idx, (hdr, inl) in enumerate(zip(header, in_lines + [None])):
        if inl is None or hdr != inl:
            if inl is None:
                inl = "<EOF>"
            logger.error(
                f"license header mismatch: %s:%d:\n"
                f" expect: %s\n"
                f" actual: %s\n"
                f"%s:%d: expected: %s",
                path,
                idx+start,
                hdr,
                inl,
                path,
                idx+start,
                hdr,
            )
            return False
    return True

def main():
    TOP_DIR = Path(os.path.relpath(Path(__file__).resolve().parents[2], Path.cwd()))
    DIRS = [Path("src")]
    LICENSE = TOP_DIR / "LICENSE"

    INCLUDES = ['*.py', '*.c', '*.h', '*.cpp', '*.hpp']
    EXCLUDES = []

    parser = argparse.ArgumentParser(
        description="Check/apply LICENSE file to sources",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--apply", action=argparse.BooleanOptionalAction, default=False,
        help="apply license, possibly modifying",
    )
    parser.add_argument(
        "--check", action=argparse.BooleanOptionalAction, default=True,
        help="check license",
    )
    parser.add_argument(
        "--license", type=str, default=str(LICENSE),
        help="license file to use",
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
    if args.check:
        checks = [check_license(args.license, path, top=args.top) for path in paths]
        failed_count = sum(not c for c in checks)
        if failed_count:
            logger.error("Checked %d files: %d errors", len(paths), failed_count)
            raise SystemExit(1)
        else:
            logger.info("Checked %d files", len(paths))
    if args.apply:
        applied = [apply_license(args.license, path, top=args.top) for path in paths]
        count = sum(applied)
        logger.info("Applied %d files: %d changed", len(paths), count)

if __name__ == "__main__":
    main()

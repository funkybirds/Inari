"""Organize DXIL IR dumps by function name for easier browsing."""
from __future__ import annotations

import argparse
import logging
import re
import shutil
from pathlib import Path
from typing import List, Optional

from tqdm import tqdm

ENTRYPOINT_REF_RE = re.compile(r"!dx\.entryPoints\s*=\s*!{!(\d+)}")
STRING_RE = re.compile(r'!"([^"]+)"')
PART_ID_RE = re.compile(r"(part\d+)", re.IGNORECASE)
SAFE_NAME_RE = re.compile(r"[^0-9A-Za-z_]+")


def extract_function_name(text: str) -> Optional[str]:
    """Return the entry-point function name recorded in the DXIL metadata."""
    entry_id_match = ENTRYPOINT_REF_RE.search(text)
    if not entry_id_match:
        return None
    entry_id = entry_id_match.group(1)
    target_prefix = f"!{entry_id}"

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(target_prefix):
            name_match = STRING_RE.search(stripped)
            if name_match:
                return name_match.group(1)
            break

    fallback = re.search(r"!dx\.entryPoints.*!\"([^\"]+)\"", text, re.DOTALL)
    if fallback:
        return fallback.group(1)
    return None


def sanitize_name(name: str) -> str:
    sanitized = SAFE_NAME_RE.sub("_", name).strip("_")
    return sanitized or "unnamed"


def extract_part_id(path: Path) -> str:
    match = PART_ID_RE.search(path.name)
    if match:
        return match.group(1)
    return path.stem


def gather_files(root: Path, pattern: str) -> List[Path]:
    return sorted(root.rglob(pattern))


def copy_ir_file(src: Path, dest_dir: Path, function_name: str, part_id: str) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{function_name}_{part_id}.txt"
    shutil.copy2(src, dest_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy DXIL IR dumps into per-function folders")
    parser.add_argument(
        "--input-root",
        type=Path,
        default=Path("Outputs/WhereWindsMeet/shader_cache_extracted"),
        help="Root directory containing *.dxil_ir.txt files (default: %(default)s)",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("Outputs/WhereWindsMeet/shader_ir"),
        help="Destination directory for organized IR files (default: %(default)s)",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="*.dxil_ir.txt",
        help="Glob pattern (relative to input root) for locating IR files",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    if not args.input_root.exists():
        raise SystemExit(f"Input root does not exist: {args.input_root}")

    files = gather_files(args.input_root, args.pattern)
    if not files:
        logging.warning("No files matched pattern %s under %s", args.pattern, args.input_root)
        return

    args.output_root.mkdir(parents=True, exist_ok=True)

    copied = 0
    skipped = 0
    for ir_path in tqdm(files, desc="Exporting shader IR", unit="file"):
        try:
            text = ir_path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            logging.error("Failed to read %s: %s", ir_path, exc)
            skipped += 1
            continue

        entry_name = extract_function_name(text)
        if not entry_name:
            logging.warning("Could not determine entry function for %s", ir_path)
            skipped += 1
            continue

        part_id = extract_part_id(ir_path)
        folder_name = ir_path.parent.name
        safe_name = sanitize_name(entry_name)

        dest_dir = args.output_root / folder_name
        try:
            copy_ir_file(ir_path, dest_dir, safe_name, part_id)
        except OSError as exc:
            logging.error("Failed to copy %s: %s", ir_path, exc)
            skipped += 1
            continue
        copied += 1

    logging.info("Copied %s IR files to %s (skipped %s)", copied, args.output_root, skipped)

if __name__ == "__main__":
    main()

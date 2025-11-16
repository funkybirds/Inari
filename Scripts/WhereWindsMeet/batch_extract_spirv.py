"""Batch splitter + DXIL/spirv extractor for Where Winds Meet caches."""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path
from typing import Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

from split_shader_cache import process_cache_file  # type: ignore  # noqa: E402
from decompile_dxil import extract_dxil  # type: ignore  # noqa: E402

DEFAULT_INPUT_DIR = SCRIPT_DIR.parent.parent / "Resources" / "WhereWindsMeet" / "dx12"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR.parent.parent / "Outputs" / "WhereWindsMeet" / "shader_cache_extracted"


def _resolve(tool: str | None, fallback: str) -> str | None:
    if tool:
        return tool
    return shutil.which(fallback)


def _iter_cache_files(input_dir: Path, single: str | None) -> Iterable[Path]:
    if single:
        target = input_dir / single
        if not target.exists():
            raise SystemExit(f"Requested cache file not found: {target}")
        yield target
        return
    yield from sorted(input_dir.glob("*.cache"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Split and extract SPIR-V IR for Where Winds Meet caches")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR, help="Directory containing *.cache files")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Destination for extracted artifacts")
    parser.add_argument("--dxc", type=str, default=None, help="Path to dxc executable (auto-detected if omitted)")
    parser.add_argument("--dxc-args", nargs="*", default=None, help="Override dxc arguments (default: dumpbin fallbacks)")
    parser.add_argument("--single", type=str, default=None, help="Process only the specified cache filename")
    parser.add_argument("--skip-split", action="store_true", help="Assume caches are already split/decompressed")
    parser.add_argument("--skip-ir", action="store_true", help="Extract DXIL bitcode without invoking llvm-dis/dxc")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    dxc = _resolve(args.dxc, "dxc")

    if args.dxc_args is None:
        dxc_arg_sets: Iterable[Iterable[str]] = (["-dumpbin"], ["-dumpbin", "-dxil"], ["-dumpbin", "-all"])
    else:
        dxc_arg_sets = (args.dxc_args,)

    caches = list(_iter_cache_files(input_dir, args.single))
    if not caches:
        logging.warning("No cache files detected under %s", input_dir)
        return

    for index, cache_file in enumerate(caches, start=1):
        logging.info("[%s/%s] Processing cache %s", index, len(caches), cache_file.name)
        cache_out_dir = output_dir / cache_file.stem

        if not args.skip_split:
            parts = process_cache_file(cache_file, output_dir)
            logging.info("Split %s into %s chunk(s)", cache_file.name, parts)

        decompressed_parts = sorted(cache_out_dir.glob("*.cache_part.lz4_decompressed"))
        if not decompressed_parts:
            logging.warning("No decompressed chunks for %s (looked in %s)", cache_file.name, cache_out_dir)
            continue

        for part_idx, dxbc_path in enumerate(decompressed_parts, start=1):
            logging.info("    [%s/%s] DXIL->IR %s", part_idx, len(decompressed_parts), dxbc_path.name)
            try:
                extract_dxil(dxbc_path, cache_out_dir, dxc, dxc_arg_sets, not args.skip_ir)
            except ValueError as err:
                logging.error("DXIL extraction failed for %s: %s", dxbc_path, err)
                continue


if __name__ == "__main__":
    main()

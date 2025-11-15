"""Utilities to split and decompress Where Winds Meet shader caches."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Iterable, Tuple

import lz4.block

DELIMITER = b"ZZZ4"
HEADER32_SIZE = 4
HEADER64_SIZE = 8


def _detect_blob_size(chunk: bytes) -> Tuple[int, int]:
    """Return (uncompressed_size, header_len)."""
    if len(chunk) < HEADER32_SIZE:
        raise ValueError("Chunk too small to contain size header")

    size32 = int.from_bytes(chunk[:HEADER32_SIZE], "little", signed=False)
    if size32 > 0:
        return size32, HEADER32_SIZE

    if len(chunk) >= HEADER64_SIZE:
        size64 = int.from_bytes(chunk[:HEADER64_SIZE], "little", signed=False)
        if size64 > 0:
            return size64, HEADER64_SIZE

    raise ValueError("Unable to determine shader blob size from chunk header")


def _iterate_cache_chunks(data: bytes) -> Iterable[bytes]:
    """Yield payload-containing chunks after the delimiter, skipping the header chunk."""
    segments = data.split(DELIMITER)
    if len(segments) <= 1:
        return
    # Discard first chunk (metadata before the first delimiter)
    for chunk in segments[1:]:
        if not chunk:
            continue
        yield chunk


def process_cache_file(cache_path: Path, output_root: Path) -> int:
    logging.info("Processing %s", cache_path.name)
    data = cache_path.read_bytes()
    chunks = list(_iterate_cache_chunks(data))

    if not chunks:
        logging.warning("No delimiter chunks detected in %s", cache_path)
        return 0

    file_output_dir = output_root / cache_path.stem
    file_output_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for index, chunk in enumerate(chunks, start=1):
        try:
            blob_size, header_len = _detect_blob_size(chunk)
        except ValueError as err:
            logging.warning("Skipping chunk %s part %s: %s", cache_path.name, index, err)
            continue

        compressed_blob = chunk[header_len:]
        if not compressed_blob:
            logging.warning("Empty blob payload for %s part %s", cache_path.name, index)
            continue

        raw_part_path = file_output_dir / f"{cache_path.stem}_part{index:04d}.cache_part"
        raw_part_path.write_bytes(compressed_blob)
        written += 1

        try:
            decompressed = lz4.block.decompress(compressed_blob, uncompressed_size=blob_size)
        except lz4.block.LZ4BlockError as err:
            logging.warning("LZ4 decompress failed for %s part %s: %s", cache_path.name, index, err)
            continue

        decompressed_path = raw_part_path.with_suffix(raw_part_path.suffix + ".lz4_decompressed")
        decompressed_path.write_bytes(decompressed)

    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Split and decompress Where Winds Meet shader caches")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("Resources/WhereWindsMeet/dx12"),
        help="Directory containing *.cache files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("Outputs/WhereWindsMeet/shader_cache_extracted"),
        help="Directory to store split and decompressed shader blobs",
    )
    parser.add_argument(
        "--single",
        type=str,
        default=None,
        help="Optional single cache filename to process (must exist in input-dir)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir

    if not input_dir.exists():
        raise SystemExit(f"Input directory not found: {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    targets = []
    if args.single:
        single_path = input_dir / args.single
        if not single_path.exists():
            raise SystemExit(f"Requested cache file not found: {single_path}")
        targets.append(single_path)
    else:
        targets.extend(sorted(input_dir.glob("*.cache")))

    if not targets:
        logging.warning("No cache files found under %s", input_dir)
        return

    total_parts = 0
    for cache_file in targets:
        total_parts += process_cache_file(cache_file, output_dir)

    logging.info("Finished. Wrote %s shader blobs from %s cache file(s).", total_parts, len(targets))


if __name__ == "__main__":
    main()

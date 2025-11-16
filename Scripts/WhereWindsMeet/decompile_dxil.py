"""DXIL extraction helpers focused on dxc + SPIR-V/IR emission."""
from __future__ import annotations

import argparse
import logging
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Dict, Iterable, Sequence, Tuple

from tqdm import tqdm

DXBC_MAGIC = b"DXBC"
DXIL_SIGNATURE = b"DXIL"
BITCODE_MAGIC = b"BC\xC0\xDE"


def _read_chunk_offsets(data: bytes) -> Iterable[int]:
    chunk_count = struct.unpack_from("<I", data, 28)[0]
    return struct.unpack_from("<" + "I" * chunk_count, data, 32)


def _parse_chunks(data: bytes) -> Dict[str, Tuple[int, bytes]]:
    chunks: Dict[str, Tuple[int, bytes]] = {}
    for offset in _read_chunk_offsets(data):
        tag = data[offset : offset + 4].decode("ascii")
        size = struct.unpack_from("<I", data, offset + 4)[0]
        payload = data[offset + 8 : offset + 8 + size]
        if tag in chunks:
            logging.warning("Duplicate chunk tag %s detected, keeping last occurrence", tag)
        chunks[tag] = (offset, payload)
    return chunks


def _extract_bitcode(dxil_chunk: bytes) -> bytes:
    if len(dxil_chunk) < 24:
        raise ValueError("DXIL chunk too small to contain header")
    if dxil_chunk[8:12] != DXIL_SIGNATURE:
        raise ValueError("Malformed DXIL chunk: missing DXIL signature")

    declared_size = struct.unpack_from("<I", dxil_chunk, 20)[0]
    bitcode_start = dxil_chunk.find(BITCODE_MAGIC)
    if bitcode_start == -1:
        raise ValueError("Bitcode magic not found inside DXIL chunk")

    bitcode = dxil_chunk[bitcode_start : bitcode_start + declared_size]
    if len(bitcode) != declared_size:
        raise ValueError("DXIL chunk truncated before bitcode ended")
    return bitcode


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    logging.info("Wrote %s (%s bytes)", path, len(payload))


def _run_tool(exe: str, args: Iterable[str], capture: bool = True) -> str | bool | None:
    cmd = [exe, *args]
    logging.debug("Running %s", " ".join(cmd))
    try:
        completed = subprocess.run(cmd, check=True, capture_output=capture, text=True)
    except FileNotFoundError:
        logging.warning("Tool %s not found on PATH", exe)
        return None
    except subprocess.CalledProcessError as err:
        logging.error("Tool %s failed: %s", exe, err)
        return None
    if capture:
        return completed.stdout
    return True


def _emit_ir_with_dxc(dxbc_path: Path, ir_path: Path, dxc: str, dxc_args: Iterable[str]) -> bool:
    output = _run_tool(dxc, [*dxc_args, str(dxbc_path)])
    if not output:
        return False
    ir_path.write_text(output)
    logging.info("Captured dxc textual output: %s", ir_path)
    return True


def extract_dxil(
    dxbc_path: Path,
    out_dir: Path,
    dxc: str | None,
    dxc_arg_sets: Iterable[Iterable[str]],
    emit_ir: bool,
) -> None:
    base_name = dxbc_path.stem
    ir_path = out_dir / f"{base_name}.dxil_ir.txt"
    dxil_path = out_dir / f"{base_name}.dxil"

    if emit_ir and ir_path.exists():
        logging.info("Skipping %s because %s already exists", dxbc_path, ir_path)
        return

    if not emit_ir and dxil_path.exists():
        logging.info("DXIL already extracted: %s", dxil_path)
        return

    data = dxbc_path.read_bytes()
    if data[:4] != DXBC_MAGIC:
        raise ValueError(f"Input is not a DXBC container: {dxbc_path}")

    chunks = _parse_chunks(data)
    dxil_chunk = chunks.get("DXIL")
    if not dxil_chunk:
        raise ValueError("DXIL chunk not found in container")

    _, payload = dxil_chunk
    try:
        bitcode = _extract_bitcode(payload)
    except ValueError as err:
        raise ValueError(f"Failed to extract DXIL bitcode: {err}") from err

    _write_bytes(dxil_path, bitcode)

    if emit_ir:
        if not dxc:
            logging.warning("Skipping textual IR dump because dxc was not found on PATH")
            return
        ir_generated = False
        for arg_set in dxc_arg_sets:
            pretty = " ".join(arg_set)
            logging.info("Trying dxc disassembly with args: %s", pretty)
            ir_generated = _emit_ir_with_dxc(dxbc_path, ir_path, dxc, arg_set)
            if ir_generated:
                break
        if not ir_generated:
            logging.warning(
                "Unable to emit textual IR automatically via dxc. Consider passing explicit --dxc-args or --skip-ir."
            )


def _gather_inputs(root: Path, pattern: str) -> Sequence[Path]:
    files = sorted(root.rglob(pattern))
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract DXIL chunks and emit dxc textual dumps")
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        help="Path to a DXBC container (e.g. *.cache_part.lz4_decompressed)",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help="Process every file under this directory matching --pattern",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="*.cache_part.lz4_decompressed",
        help="Glob used with --input-dir (default: %(default)s)",
    )
    parser.add_argument("--out-dir", type=Path, default=None, help="Directory for extracted artifacts")
    parser.add_argument("--dxc", type=str, default=None, help="Path to dxc executable (auto-detected if omitted)")
    parser.add_argument(
        "--dxc-args",
        nargs="*",
        default=None,
        help="Additional arguments passed to dxc after the executable (default: -dumpbin -dxil)",
    )
    parser.add_argument(
        "--skip-ir",
        action="store_true",
        help="Skip attempts to produce human-readable IR (default is to emit IR when tooling is available)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    multi_mode = args.input_dir is not None
    if (args.input is None and not multi_mode) or (args.input is not None and multi_mode):
        raise SystemExit("Specify exactly one of a single input path or --input-dir")

    log_level: int
    if args.verbose and not multi_mode:
        log_level = logging.DEBUG
    elif multi_mode:
        log_level = logging.WARNING
    else:
        log_level = logging.INFO

    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    if args.verbose and multi_mode:
        logging.warning("Verbose flag detected, but debug logs are suppressed while tqdm progress is active")

    target_paths: Sequence[Path]
    if multi_mode:
        if not args.input_dir.exists():
            raise SystemExit(f"Input directory does not exist: {args.input_dir}")
        target_paths = _gather_inputs(args.input_dir, args.pattern)
        if not target_paths:
            logging.warning("No files matched pattern %s under %s", args.pattern, args.input_dir)
            return
    else:
        dxbc_path = args.input
        if not dxbc_path or not dxbc_path.exists():
            raise SystemExit(f"Input file does not exist: {dxbc_path}")
        target_paths = [dxbc_path]

    out_dir_override = args.out_dir
    if out_dir_override:
        out_dir_override.mkdir(parents=True, exist_ok=True)

    dxc = args.dxc or shutil.which("dxc")

    if args.dxc_args is None:
        dxc_arg_sets = (["-dumpbin"], ["-dumpbin", "-dxil"], ["-dumpbin", "-all"])
    else:
        dxc_arg_sets = (args.dxc_args,)

    emit_ir = not args.skip_ir

    iterator = tqdm(target_paths, desc="DXBC caches", unit="file") if multi_mode else target_paths
    for dxbc_path in iterator:
        if out_dir_override:
            out_dir = out_dir_override
        else:
            out_dir = dxbc_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            extract_dxil(dxbc_path, out_dir, dxc, dxc_arg_sets, emit_ir)
        except ValueError as err:
            logging.error("Failed to process %s: %s", dxbc_path, err)
            continue


if __name__ == "__main__":
    main()

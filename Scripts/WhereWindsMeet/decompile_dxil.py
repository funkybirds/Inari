"""DXIL extraction and optional disassembly helpers for DXBC containers."""
from __future__ import annotations

import argparse
import logging
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Dict, Iterable, Tuple

try:  # optional dependency used for built-in IR dumps
    import llvmlite.binding as llvm  # type: ignore
except ImportError:  # pragma: no cover - optional path
    llvm = None

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


def _emit_ir_with_llvm_dis(dxil_path: Path, ll_path: Path, llvm_dis: str) -> bool:
    result = _run_tool(llvm_dis, [str(dxil_path), "-o", str(ll_path)], capture=False)
    if result:
        logging.info("Generated LLVM IR: %s", ll_path)
        return True
    return False


def _emit_ir_with_llvmlite(dxil_path: Path, ll_path: Path) -> bool:
    if llvm is None:
        return False
    try:
        module = llvm.parse_bitcode(dxil_path.read_bytes())
    except RuntimeError as err:
        logging.warning("llvmlite could not parse DXIL bitcode: %s", err)
        return False
    ll_path.write_text(str(module))
    logging.info("Generated LLVM IR via llvmlite: %s", ll_path)
    return True


def _emit_ir_with_dxc(dxbc_path: Path, ir_path: Path, dxc: str) -> bool:
    output = _run_tool(dxc, ["-dumpbin", "-dxil", str(dxbc_path)])
    if not output:
        return False
    ir_path.write_text(output)
    logging.info("Captured DXIL disassembly via dxc: %s", ir_path)
    return True


def extract_dxil(
    dxbc_path: Path,
    out_dir: Path,
    llvm_dis: str | None,
    dxc: str | None,
    emit_ir: bool,
) -> None:
    data = dxbc_path.read_bytes()
    if data[:4] != DXBC_MAGIC:
        raise SystemExit(f"Input is not a DXBC container: {dxbc_path}")

    chunks = _parse_chunks(data)
    dxil_chunk = chunks.get("DXIL")
    if not dxil_chunk:
        raise SystemExit("DXIL chunk not found in container")

    _, payload = dxil_chunk
    try:
        bitcode = _extract_bitcode(payload)
    except ValueError as err:
        raise SystemExit(f"Failed to extract DXIL bitcode: {err}") from err

    base_name = dxbc_path.stem
    dxil_path = out_dir / f"{base_name}.dxil"
    _write_bytes(dxil_path, bitcode)

    if emit_ir:
        ir_generated = False
        ll_path = out_dir / f"{base_name}.ll"
        if not ir_generated:
            ir_generated = _emit_ir_with_llvmlite(dxil_path, ll_path)
        if not ir_generated and llvm_dis:
            ir_generated = _emit_ir_with_llvm_dis(dxil_path, ll_path, llvm_dis)
        if not ir_generated and dxc:
            ir_path = out_dir / f"{base_name}.dxil_ir.txt"
            ir_generated = _emit_ir_with_dxc(dxbc_path, ir_path, dxc)
        if not ir_generated:
            logging.warning(
                "Unable to emit human-readable IR automatically. Install llvm-dis or dxc and rerun, or pass --skip-ir."
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract DXIL chunks and optionally disassemble them")
    parser.add_argument("input", type=Path, help="Path to a DXBC container (e.g. *.cache_part.lz4_decompressed)")
    parser.add_argument("--out-dir", type=Path, default=None, help="Directory for extracted artifacts")
    parser.add_argument("--llvm-dis", type=str, default=None, help="Path to llvm-dis executable (auto-detected if omitted)")
    parser.add_argument("--dxc", type=str, default=None, help="Path to dxc executable (auto-detected if omitted)")
    parser.add_argument(
        "--skip-ir",
        action="store_true",
        help="Skip attempts to produce human-readable IR (default is to emit IR when tooling is available)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s: %(message)s")

    dxbc_path: Path = args.input
    if not dxbc_path.exists():
        raise SystemExit(f"Input file does not exist: {dxbc_path}")

    out_dir = args.out_dir or dxbc_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    llvm_dis = args.llvm_dis or shutil.which("llvm-dis")
    dxc = args.dxc or shutil.which("dxc")

    extract_dxil(dxbc_path, out_dir, llvm_dis, dxc, not args.skip_ir)


if __name__ == "__main__":
    main()

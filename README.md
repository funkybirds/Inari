# Project Inari

Utilities and scripts for extracting and reverse engineering game resources.

## Environment Setup

```powershell
conda create -n inari_env python=3.13
conda activate inari_env
pip install -r requirements.txt
```

## Shader Cache Extraction (Where Winds Meet CN)

1. Ensure the original `.cache` files live under `Resources/WhereWindsMeet/dx12/`.
2. Activate `inari_env` and install dependencies from `requirements.txt`.
3. Run the splitter utility:

```powershell
python Scripts/WhereWindsMeet/split_shader_cache.py --verbose
```

Each cache file is split into individual `*.cache_part` blobs and immediately decompressed into companion `.cache_part.lz4_decompressed` files under `Outputs/WhereWindsMeet/shader_cache_extracted/<cache_name>/`.

## DXIL Decompilation Helper

Use the DXIL helper to extract the DXIL chunk from any `.cache_part.lz4_decompressed` (or generic `.dxbc`) file. The script writes the raw DXIL bitcode (`*.dxil`) and automatically tries to emit human-readable IR via `llvm-dis` (preferred) or `dxc -dumpbin -dxil` when either executable is available on your PATH:

```powershell
python Scripts/WhereWindsMeet/decompile_dxil.py Outputs/WhereWindsMeet/shader_cache_extracted/DLSS/DLSS_part0001.cache_part.lz4_decompressed --verbose
```

- Flags:
	- `--out-dir <dir>`: custom destination for the generated `.dxil`/`.ll`/`.dxil_ir.txt` files (defaults to the source directory).
	- `--llvm-dis <path>` / `--dxc <path>`: override auto-detected tool locations.
	- `--skip-ir`: disable IR generation attempts if you only need the raw bitcode.
- Prerequisites for IR output: install either LLVM tools (`llvm-dis`) or the DirectX Shader Compiler (`dxc`). If neither tool is present the script still emits the `.dxil` bitcode and logs a reminder to add one of the disassemblers.

# Project Inari

## Architecture Overview
Mixed automation project for resource extraction and reverse engineering.
File architecture is as follows:

```
Project Inari
│
├── AGENTS.md                   # Documentation for agents
├── Outputs                     # Output directory for processed files
│   ├── GenshinImpact           # Processed files for Genshin Impact
│   ├── DemonMayCry5            # Processed files for Demon May Cry 5
│   └── ...                     # Other game outputs
├── Resources                   # Resource files for various games
│   ├── GenshinImpact           # Genshin Impact resources
│   ├── DemonMayCry5            # Demon May Cry 5 resources
│   └── ...                     # Other game resources
├── Scripts                     # Scripts for processing and extraction
│   ├── GenshinImpact           # Scripts for Genshin Impact
│   |   ├── extract_shaders.py  # Example script for shader extraction
│   |   └── ...                 # Other scripts
│   ├── DemonMayCry5            # Scripts for Demon May Cry 5
│   └── ...                     # Other game scripts
├── README.md                   # Project overview and instructions
└── .gitignore                  # Git ignore file
```

## Task1: Decompile Shader Caches (Where Winds Meet CN)

### Status
Splitter and DXIL helper are production-ready; full cache corpus can be processed via batch mode.

### Environment & Dependencies
- `.gitignore` ignores `Outputs/` and `Resources/`.
- Recommended environment: `conda create -n inari_env python=3.13`.
- Activate env and install deps: `pip install -r requirements.txt` (installs `lz4`, `tqdm`).

### Step A: Split cache containers
1. Source caches reside under `Resources/WhereWindsMeet/dx12/`.
2. Run the splitter (defaults are pre-configured):

   ```powershell
   python Scripts/WhereWindsMeet/split_shader_cache.py --verbose
   ```

   - Handles `ZZZ4` delimiter + LZ4 in one pass.
   - Drops header chunk, then emits sequential `..._part####.cache_part` plus decompressed `..._part####.cache_part.lz4_decompressed` into `Outputs/WhereWindsMeet/shader_cache_extracted/<cache_name>/`.

### Step B: Extract DXIL + textual IR
The DXIL helper is now **dxc-only** and supports single-file or directory traversal with tqdm.

#### Single file

```powershell
python Scripts/WhereWindsMeet/decompile_dxil.py Outputs/WhereWindsMeet/shader_cache_extracted/DLSS/DLSS_part0001.cache_part.lz4_decompressed --verbose
```

- Produces `<file>.dxil` plus `<file>.dxil_ir.txt` (captured from `dxc -dumpbin`).
- Flags: `--out-dir`, `--dxc`, `--dxc-args`, `--skip-ir`.
- Default dxc argument order tries `-dumpbin`, then `-dumpbin -dxil`, then `-dumpbin -all`.

#### Entire cache corpus → SPIR-V text dumps

```powershell
python Scripts/WhereWindsMeet/decompile_dxil.py --input-dir Outputs/WhereWindsMeet/shader_cache_extracted --pattern "*.cache_part.lz4_decompressed" --dxc-args -dumpbin
```

- tqdm renders progress (debug logs suppressed automatically).
- Warnings/errors still surface for failed invocations; rerunning is safe (files overwrite).
- Use `--out-dir <dir>` to redirect all artifacts away from the source tree if desired.

### Validation & Follow-up
- Spot check generated `.dxil_ir.txt` assets to confirm the desired SPIR-V output is captured (e.g., `DLSS_part0001.cache_part.dxil_ir.txt`).
- If dxc reports missing metadata, verify `dxcompiler.dll`/`dxil.dll` are co-located with the executable.
- Any additional tooling steps (Shader Conductor, RenderDoc, etc.) should consume the produced `.dxil` or textual dumps as needed.
    



# Project Inari

## Architecture Overview
An mixed project for game resource extraction and reverse engineering.
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

## Task1: Decompile Shader Caches (For Game `Where Winds Meet CN`)

### Status
Automation ready (run splitter script as needed)

### Steps to Parse Shader Caches
1. **Set Up Environment**:
    - `.gitignore` now ignores `Outputs/` and `Resources/` per repository policy.
    - Create conda environment with Python 3.13, named `inari_env`.
    - Activate the conda environment and run `pip install -r requirements.txt` (installs `lz4`).

2. **Identify Shader Cache Files**: Locate the shader cache files within the project directory (Path: `Resources/WhereWindsMeet/dx12`).

3. **Split Shader Cache Files**: Use `Scripts/WhereWindsMeet/split_shader_cache.py` to handle the delimiter logic (`ZZZ4` / `0x5A5A5A34`) and LZ4 decompression automatically:
    - Run `python Scripts/WhereWindsMeet/split_shader_cache.py --verbose` (input/output paths default to the directories listed above).
    - The script discards the first chunk, inspects the first 4 or 8 bytes to determine blob size, writes `${original}_part####.cache_part`, and creates `${original}_part####.cache_part.lz4_decompressed`.
    - Outputs land in `Outputs/WhereWindsMeet/shader_cache_extracted/<cache_name>/`.

### Shader Analysis Notes (DLSS sample)
- `DLSS_part0001.cache_part.lz4_decompressed` is a 7.2 KB DXBC container carrying DXIL bytecode.
- Chunk table: `SFI0`, `ISG1`, `OSG1`, `PSV0`, `STAT`, `ILDN`, `HASH`, `DXIL`; use this to confirm shader model metadata.
- Next steps:
    1. Run `python Scripts/WhereWindsMeet/decompile_dxil.py <path-to-cache_part.lz4_decompressed>` to emit the raw DXIL blob plus `.ll` IR whenever `llvm-dis`/`dxc` is available.
    2. Feed the generated `.ll` (or the `.dxil` bitcode) to Shader Conductor / `llvm-dis` / RenderDoc if further conversion is required.
    3. When editing, revalidate via `dxc` to regenerate the HASH chunk before reinsertion.
    



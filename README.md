# Project Inari

Internal automation toolkit for processing proprietary binary assets. Detailed, task-specific guidance lives in `AGENTS.md`; this README only covers the shared boilerplate required to work inside the repository.

## Environment

```powershell
conda create -n inari_env python=3.13
conda activate inari_env
pip install -r requirements.txt
```

The dependency list is deliberately small (core runtime helpers plus CLI quality-of-life tooling) so that each workstation can be brought online quickly.

## Workflow

1. Clone the repository and complete the environment bootstrap above.
2. Review `AGENTS.md` for the current objective, expected input locations, and command lines to run.
3. Drop all generated artifacts under `Outputs/` (already ignored) to keep the working tree clean.
4. Contribute updates back to `AGENTS.md` whenever procedures change so future operators stay in sync.

This top-level README intentionally omits any project-specific techniques or datasets; always refer to `AGENTS.md` (or the issue tracker) for the live runbook.

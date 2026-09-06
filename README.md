# Modular Tank (OpenUSD Learning Project)

A modular, animated military tank built with the OpenUSD Python API (`pxr`),
following the 6-stage compositional pipeline described in `CLAUDE.md`:
tread link -> track (point instancing) -> chassis -> turret (variants) ->
tank assembly -> rigging -> motion.

![Tank demo](demos/modular_tank_anim.gif)

## Prerequisites

This project uses **one conda environment for everything** -- both running
the generator scripts and validating the output -- plus [uv](https://docs.astral.sh/uv/)
wired to that same environment for fast, lockfile-driven invocation.

Why conda and not plain `uv sync` / PyPI: the PyPI `usd-core` wheel (what a
plain `pyproject.toml` dependency would pull in) is a stripped "core" build --
it has no `usdchecker` CLI and no Hydra. conda-forge's `openusd` package is
the full build: it includes `usdchecker` (needed for step 3) and, as a bonus,
`usdview` and Hydra, and it's published for Windows, macOS (Intel/ARM), and
Linux (x86_64/ARM), so this isn't Windows- or machine-specific.

**One-time setup** (requires [conda or mamba](https://github.com/conda-forge/miniforge)):

```powershell
conda env create -f environment.yml -p ./.conda-env
```

This creates a project-local `.conda-env/` (gitignored) rather than a
globally-named environment, so the path below is the same on every machine
regardless of where conda itself is installed.

Then, once per shell session, point `uv` at that same environment instead of
letting it create its own separate `.venv`:

```powershell
$env:UV_PROJECT_ENVIRONMENT = ".conda-env"
```

(macOS/Linux: `export UV_PROJECT_ENVIRONMENT=.conda-env`.) With that set,
`uv run` below transparently uses `.conda-env`'s Python (and its
conda-installed `pxr`) instead of managing its own venv.

> **Don't run a bare `uv sync` or `uv add` against this environment.**
> `pyproject.toml` intentionally declares no dependencies -- `openusd` (conda)
> already provides everything steps 1-2 need. `uv sync`'s default is an
> *exact* sync, which removes any package not declared in `pyproject.toml`;
> pointed at `.conda-env`, that would strip out `usdview`'s own
> conda-installed dependencies (PySide6, PyOpenGL). Plain `uv run` (used
> below) is safe -- it only installs what's missing, it doesn't prune. If you
> ever add a real uv dependency, sync with `uv sync --inexact`.

## 1. Generate the per-stage `.usda` files

```powershell
uv run python main.py
```

Runs the six generator scripts in order and (re)writes every `out/*.usda`
file: `tread_link.usda`, `track.usda`, `chassis.usda`, `turret.usda`,
`tank_assembly.usda`, `rigged_tank.usda`, `tank_motion.usda`. `tank_motion.usda`
is the composed root -- it references everything else and carries the 100-frame
shot animation.

## 2. Compile a single `.usdc` for Blender / glTF viewers

`tank_motion.usda` alone will not render correctly in most DCC tools if opened
as-is: it composes multiple referenced layers, and its two tread-link
`PointInstancer`s are not reliably supported outside a full USD-aware renderer
(Blender's importer, `usd2gltf`, and three.js-based viewers like
usdz-viewer.net each handle `PointInstancer` differently or not at all -- see
the `usd-dcc-export` Claude skill for the full write-up). Compile a
self-contained, DCC-safe file with:

```powershell
uv run python src/export_for_dcc.py
```

This bakes both tread-link `PointInstancer`s into explicit, individually
time-animated prims (no instancing left in the output) and flattens the whole
composition into `out/tank_final.usdc` -- **this is the file to import**, not
any of the per-stage `.usda` files.

## 3. Validate (optional but recommended after any change)

```powershell
conda run -p ./.conda-env usdchecker out/tank_final.usdc
```

Should print `Success!`. This only confirms the file is spec-valid USD, not
that every consumer will render it identically -- see step 4's caveats.

As a bonus, `.conda-env` also has `usdview` (Hydra-based), so you can inspect
the result directly instead of only Blender/online viewers:

```powershell
conda run -p ./.conda-env usdview out/tank_final.usdc
```

## 4. Import into Blender or an online viewer

- **Blender**: File -> Import -> Universal Scene Description, select
  `out/tank_final.usdc`. Every part (hull, turret, wheels, both tread-link
  chains) should appear fully colored and the 100-frame driving/rolling
  animation should play.
- **usdz-viewer.net** (or similar three.js-based viewers): drag in
  `tank_final.usdc` directly. Colors and geometry show; if you use its
  "download as glTF/GLB" feature, note that export is a **static snapshot** --
  none of the USD time-sampled animation survives that particular round trip,
  and the downloaded file may be plain-text glTF JSON despite the `.glb` name
  (still opens fine in Blender via content-sniffing).

## Regenerating after an edit

Any change to a generator script under `src/` (chassis, track, turret,
master assembly, rigging, or motion) requires re-running **both** steps 1 and
2 above, in order -- `main.py` first (source of truth), then
`export_for_dcc.py` (derived export artifact). `out/` is gitignored; nothing
in it is checked in.

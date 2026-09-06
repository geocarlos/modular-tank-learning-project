# Modular Tank (OpenUSD Learning Project)

A modular, animated military tank built with the OpenUSD Python API (`pxr`),
following the 6-stage compositional pipeline described in `CLAUDE.md`:
tread link -> track (point instancing) -> chassis -> turret (variants) ->
tank assembly -> rigging -> motion.

![Tank demo](demos/modular_tank_anim.gif)

## Prerequisites

The system `python` on this machine does not have `pxr` installed (or has a
mismatched build). Use the bundled USD-Python distribution instead:

```powershell
$env:USD_INSTALL_DIR = "C:\Users\geocarlos\workspace\usd_root"
$env:PATH = "$env:USD_INSTALL_DIR\lib;$env:USD_INSTALL_DIR\plugin\usd;$env:USD_INSTALL_DIR\bin;$env:USD_INSTALL_DIR\python;$env:PATH"
$env:PYTHONPATH = "$env:USD_INSTALL_DIR\lib\python;$env:PYTHONPATH"
```

Run this once per shell session before any command below. All commands use
`& "$env:USD_INSTALL_DIR\python\python.exe"` rather than plain `python` so
they resolve to that same matching build.

## 1. Generate the per-stage `.usda` files

```powershell
& "$env:USD_INSTALL_DIR\python\python.exe" main.py
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
& "$env:USD_INSTALL_DIR\python\python.exe" src\export_for_dcc.py
```

This bakes both tread-link `PointInstancer`s into explicit, individually
time-animated prims (no instancing left in the output) and flattens the whole
composition into `out/tank_final.usdc` -- **this is the file to import**, not
any of the per-stage `.usda` files.

## 3. Validate (optional but recommended after any change)

```powershell
cmd /c "$env:USD_INSTALL_DIR\scripts\usdchecker.bat" out\tank_final.usdc
```

Should print `Success!`. This only confirms the file is spec-valid USD, not
that every consumer will render it identically -- see step 4's caveats.

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

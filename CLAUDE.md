# OpenUSD Modular Tank Project

## Project Context
This project constructs a modular, animated military tank using the OpenUSD Python API (`pxr`). It follows a strict 6-stage compositional pipeline:
1. `tread_link.usda` (Base Geometry)
2. `track.usda` (Point Instancing)
3. `chassis.usda` (Base Geometry)
4. `turret.usda` (VariantSets for Weapons)
5. `tank_assembly.usda` (References & Overrides)
6. `rigged_tank.usda` (Explicit xformOpOrder Rigging)
7. `tank_motion.usda` (Time-Sampled Animation)

## Build Commands
* Run python generator scripts (e.g., `python src/chassis.py`)
* Output files must ALWAYS be written to the `out/` directory.
* View results: `usdview out/tank_motion.usda`

## OpenUSD Python Coding Guidelines
* **Imports:** Standard imports should be `from pxr import Usd, UsdGeom, Gf, Vt, Sdf`.
* **Geometry:** Use `UsdGeom` classes. Move from basic Primitives (Cube, Cylinder) to `UsdGeom.Mesh` with explicit `Vt.Vec3fArray` points and face indices for complex geometry.
* **Transforms:** 
  - For static placement: Use `UsdGeom.XformCommonAPI`.
  - For animated/rigged parts: Use explicit `xformOp` methods (e.g., `AddTranslateOp()`, `AddRotateYOp(opSuffix="yaw")`) and ensure they are properly registered in the `xformOpOrder`.
* **Up Axis & Scale:** Always configure new stages with `UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)` and `UsdGeom.SetStageMetersPerUnit(stage, 1.0)`.
* **Immutability:** Do not write shot-level animation directly into the component assets. Keep time samples strictly in `tank_motion.usda`.

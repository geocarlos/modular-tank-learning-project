from pxr import Gf, Usd, UsdGeom

# 1. Initialize Stage and Set Global Metadata
stage = Usd.Stage.CreateNew("out/chassis.usda")
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)

# 2. Define Root Xform Prim for the Asset
chassis_root = UsdGeom.Xform.Define(stage, "/Chassis")
stage.SetDefaultPrim(chassis_root.GetPrim())

# 3. Create a Cube Prim representing the Main Body Hull
body_mesh = UsdGeom.Cube.Define(stage, "/Chassis/Body")

# 4. Transform the Body (Scale: Length 4m, Height 1m, Width 2.5m)
xform_api = UsdGeom.XformCommonAPI(body_mesh)
xform_api.SetScale(Gf.Vec3f(2.0, 0.5, 1.25))
xform_api.SetTranslate(Gf.Vec3d(0.0, 0.5, 0.0))  # Lift above ground

# 5. Write Stage to Disk
stage.GetRootLayer().Save()
print("Successfully generated chassis.usda")
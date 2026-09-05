from pxr import Gf, Usd, UsdGeom

# 1. Initialize Stage
stage = Usd.Stage.CreateNew("out/rigged_tank.usda")
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)

# 2. Root Tank Prim
tank_root = UsdGeom.Xform.Define(stage, "/Tank")
stage.SetDefaultPrim(tank_root.GetPrim())

# 3. Reference Static Components (Chassis & Tracks)
chassis = stage.DefinePrim("/Tank/Chassis")
chassis.GetReferences().AddReference("chassis.usda")

left_track = UsdGeom.Xform.Define(stage, "/Tank/LeftTrack")
left_track.GetPrim().GetReferences().AddReference("track.usda")
UsdGeom.XformCommonAPI(left_track).SetTranslate(Gf.Vec3d(0.0, 0.0, -1.5))

right_track = UsdGeom.Xform.Define(stage, "/Tank/RightTrack")
right_track.GetPrim().GetReferences().AddReference("track.usda")
UsdGeom.XformCommonAPI(right_track).SetTranslate(Gf.Vec3d(0.0, 0.0, 1.5))

# 4. Create Articulated Turret Mount Xform Node
turret_mount = UsdGeom.Xform.Define(stage, "/Tank/TurretMount")
turret_xformable = UsdGeom.Xformable(turret_mount)

# Build explicit xformOp stack: Translate to position, then Rotate Y for Yaw
trans_op = turret_xformable.AddTranslateOp()
yaw_op = turret_xformable.AddRotateYOp(opSuffix="yaw")

# Assign values (Offset on top of chassis, Rotate Yaw 35 degrees)
trans_op.Set(Gf.Vec3d(0.0, 1.0, 0.0))
yaw_op.Set(35.0)

# 5. Reference Turret Geometry under the Articulated Mount
turret_asset = stage.DefinePrim("/Tank/TurretMount/TurretAsset")
turret_asset.GetReferences().AddReference("turret.usda")
turret_asset.GetVariantSet("weaponType").SetVariantSelection("DualAutocannon")

# 6. Save Stage
stage.GetRootLayer().Save()
print("Successfully generated out/rigged_tank.usda")
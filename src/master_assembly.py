from pxr import Gf, Usd, UsdGeom

# 1. Initialize Master Stage
stage = Usd.Stage.CreateNew("out/tank_assembly.usda")
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)

# 2. Define Root Xform for Master Asset
tank_root = UsdGeom.Xform.Define(stage, "/Tank")
stage.SetDefaultPrim(tank_root.GetPrim())

# 3. Reference Chassis Asset
chassis_prim = stage.DefinePrim("/Tank/Chassis")
chassis_prim.GetReferences().AddReference("chassis.usda")

# 4. Reference Left and Right Tracks
# track.usda's tread run and road wheels are authored along local X, so a 90 degree
# yaw is needed to align the tread direction with the chassis's forward (Z) axis.
# The tracks must then be offset laterally along X (outboard of the hull, which is
# 2.5m / half_width=1.25 wide) so they flank the hull rather than sitting on its centerline.
track_lateral_offset = 1.5
left_track = UsdGeom.Xform.Define(stage, "/Tank/Tracks/LeftTrack")
left_track.GetPrim().GetReferences().AddReference("track.usda")
left_track_api = UsdGeom.XformCommonAPI(left_track)
left_track_api.SetTranslate(Gf.Vec3d(-track_lateral_offset, 0.0, 0.0))
left_track_api.SetRotate(Gf.Vec3f(0.0, 90.0, 0.0))

right_track = UsdGeom.Xform.Define(stage, "/Tank/Tracks/RightTrack")
right_track.GetPrim().GetReferences().AddReference("track.usda")
right_track_api = UsdGeom.XformCommonAPI(right_track)
right_track_api.SetTranslate(Gf.Vec3d(track_lateral_offset, 0.0, 0.0))
right_track_api.SetRotate(Gf.Vec3f(0.0, 90.0, 0.0))

# 5. Reference Turret and Position on Chassis Top
turret_xform = UsdGeom.Xform.Define(stage, "/Tank/Turret")
turret_prim = turret_xform.GetPrim()
turret_prim.GetReferences().AddReference("turret.usda")
UsdGeom.XformCommonAPI(turret_xform).SetTranslate(Gf.Vec3d(0.0, 1.0, 0.0))

# 6. Apply Variant Override on the Referenced Turret Prim
turret_prim.GetVariantSet("weaponType").SetVariantSelection("DualAutocannon")

# 7. Save Stage
stage.GetRootLayer().Save()
print("Successfully generated out/tank_assembly.usda")
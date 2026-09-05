from pxr import Gf, Usd, UsdGeom

# 1. Initialize Animation Stage
stage = Usd.Stage.CreateNew("out/tank_motion.usda")
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)

# 2. Configure Time/Frame Rate Metadata (Frames 1 to 100 at 24fps)
stage.SetStartTimeCode(1.0)
stage.SetEndTimeCode(100.0)
stage.SetFramesPerSecond(24.0)
stage.SetTimeCodesPerSecond(24.0)

# 3. Create Shot Root Prim and Reference Rigged Tank
tank_shot_xform = UsdGeom.Xform.Define(stage, "/World/TankShot")
stage.SetDefaultPrim(tank_shot_xform.GetPrim())

tank_ref = stage.DefinePrim("/World/TankShot/RiggedTank")
tank_ref.GetReferences().AddReference("rigged_tank.usda")

# 4. Get Core Transform Ops for Shot-Level Animation
# Root Movement: Drive entire vehicle forward along Z axis
root_xformable = UsdGeom.Xformable(tank_shot_xform)
root_trans_op = root_xformable.AddTranslateOp()

# Turret Movement: Fetch the turret mount prim from the referenced rig
turret_mount_prim = stage.GetPrimAtPath("/World/TankShot/RiggedTank/TurretMount")
turret_xformable = UsdGeom.Xformable(turret_mount_prim)

# Fetch the existing 'xformOp:rotateY:yaw' op created in Step 5
yaw_op = None
for op in turret_xformable.GetOrderedXformOps():
    if op.GetOpName() == "xformOp:rotateY:yaw":
        yaw_op = op
        break

# 5. Author Time Samples across 100 Frames
for frame in range(1, 101):
    time_code = Usd.TimeCode(frame)
    t = (frame - 1) / 99.0  # Normalized progress [0.0 to 1.0]

    # Drive vehicle forward 15 meters along Z
    z_pos = t * 15.0
    root_trans_op.Set(Gf.Vec3d(0.0, 0.0, z_pos), time_code)

    # Sweep turret from 0 degrees to 90 degrees
    turret_yaw = t * 90.0
    if yaw_op:
        yaw_op.Set(turret_yaw, time_code)

# 6. Save Stage
stage.GetRootLayer().Save()
print("Successfully generated out/tank_motion.usda")
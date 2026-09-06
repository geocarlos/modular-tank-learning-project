import math

from pxr import Gf, Usd, UsdGeom

import track

# 1. Initialize Animation Stage
stage = Usd.Stage.CreateNew("out/tank_motion.usda")
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)

# 2. Configure Time/Frame Rate Metadata (Frames 1 to 265 at 24fps)
stage.SetStartTimeCode(1.0)
stage.SetEndTimeCode(265.0)
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

# Rolling parts of each track: the road wheels, drive sprocket and idler
# wheel all spin about their own local Z axis, plus the tread PointInstancer
# itself, whose positions/orientations are re-evaluated per frame by shifting
# every link along the same stadium loop built in track.py.
wheel_names = [f"Wheel_{i}" for i in range(track.NUM_ROAD_WHEELS)] + ["DriveSprocket", "IdlerWheel"]
wheel_radii = {f"Wheel_{i}": track.ROAD_WHEEL_RADIUS for i in range(track.NUM_ROAD_WHEELS)}
wheel_radii["DriveSprocket"] = track.PULLEY_RADIUS
wheel_radii["IdlerWheel"] = track.PULLEY_RADIUS

track_apis = []
for track_name in ("LeftTrack", "RightTrack"):
    wheel_apis = []
    for wheel_name in wheel_names:
        wheel_prim = stage.GetPrimAtPath(
            f"/World/TankShot/RiggedTank/{track_name}/RoadWheels/{wheel_name}"
        )
        wheel_apis.append((UsdGeom.XformCommonAPI(wheel_prim), wheel_radii[wheel_name]))
    instancer = UsdGeom.PointInstancer(
        stage.GetPrimAtPath(f"/World/TankShot/RiggedTank/{track_name}/Instancer")
    )
    track_apis.append((wheel_apis, instancer))

# 5. Author Time Samples across 265 Frames
for frame in range(1, 266):
    time_code = Usd.TimeCode(frame)
    t = (frame - 1) / 264.0  # Normalized progress [0.0 to 1.0]

    # Drive vehicle from 15 meters behind origin to 25 meters past it
    # (starts/ends off camera, same speed as before over a longer path)
    z_pos = -15.0 + t * 40.0
    root_trans_op.Set(Gf.Vec3d(0.0, 0.0, z_pos), time_code)

    # Sweep turret from 0 degrees to 90 degrees
    turret_yaw = t * 90.0
    if yaw_op:
        yaw_op.Set(turret_yaw, time_code)

    # Roll the tracks: wheels/sprocket/idler spin at (distance / radius)
    # radians, and the tread links re-trace the loop shifted by the same
    # distance, so the belt appears to roll without slipping under the hull.
    positions, orientations = track.compute_tread_transforms(phase=z_pos)
    for wheel_apis, instancer in track_apis:
        for wheel_api, radius in wheel_apis:
            spin_deg = math.degrees(z_pos / radius)
            wheel_api.SetRotate(Gf.Vec3f(0.0, 0.0, spin_deg), time=time_code)
        instancer.GetPositionsAttr().Set(positions, time_code)
        instancer.GetOrientationsAttr().Set(orientations, time_code)

# 6. Save Stage
stage.GetRootLayer().Save()
print("Successfully generated out/tank_motion.usda")
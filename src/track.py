import math

from pxr import Gf, Usd, UsdGeom, Vt

# ---------------------------------------------------------
# Shared loop geometry -- module-level constants + a pure position/orientation
# function so tank_motion.py can import this file (without re-running the
# stage-authoring code below, which is guarded by __main__) and recompute the
# same tread path with a phase offset to animate the belt rolling.
# ---------------------------------------------------------
NUM_TREAD_LINKS = 30
ROAD_WHEEL_RADIUS = 0.18
NUM_ROAD_WHEELS = 6
ROAD_WHEEL_SPAN = 2.75  # distance covered by the road-wheel row on the ground
PULLEY_RADIUS = 0.28  # shared radius of the rear drive sprocket and front idler
PULLEY_MARGIN = 0.35  # how far beyond the road-wheel row each pulley center sits

WHEEL_RUN_START = -ROAD_WHEEL_SPAN / 2.0
WHEEL_SPACING = ROAD_WHEEL_SPAN / (NUM_ROAD_WHEELS - 1)

# Pulley centers: A = rear (drive sprocket), B = front (idler). The tread loop
# is the stadium (rounded rectangle) traced by a belt of radius PULLEY_RADIUS
# wrapped around two pulleys of that same radius, PULLEY_STRAIGHT_LENGTH apart.
PULLEY_CENTER_A_X = WHEEL_RUN_START - PULLEY_MARGIN
PULLEY_CENTER_B_X = WHEEL_RUN_START + ROAD_WHEEL_SPAN + PULLEY_MARGIN
PULLEY_STRAIGHT_LENGTH = PULLEY_CENTER_B_X - PULLEY_CENTER_A_X
LOOP_TOTAL_LENGTH = 2.0 * PULLEY_STRAIGHT_LENGTH + 2.0 * math.pi * PULLEY_RADIUS
LINK_SPACING = LOOP_TOTAL_LENGTH / NUM_TREAD_LINKS


def _loop_point(s):
    """Map arc-length s (wrapped to the loop's total length) to a local
    (x, y, tangent_angle_degrees) on the stadium tread path: bottom straight
    run -> arc around the front idler -> top straight run -> arc around the
    rear sprocket -> back to the start."""
    s = s % LOOP_TOTAL_LENGTH
    half_circ = math.pi * PULLEY_RADIUS

    if s < PULLEY_STRAIGHT_LENGTH:
        x = PULLEY_CENTER_A_X + s
        y = 0.0
        angle = 0.0
    elif s < PULLEY_STRAIGHT_LENGTH + half_circ:
        theta = -math.pi / 2.0 + (s - PULLEY_STRAIGHT_LENGTH) / PULLEY_RADIUS
        x = PULLEY_CENTER_B_X + PULLEY_RADIUS * math.cos(theta)
        y = PULLEY_RADIUS + PULLEY_RADIUS * math.sin(theta)
        angle = math.degrees(theta) + 90.0
    elif s < 2.0 * PULLEY_STRAIGHT_LENGTH + half_circ:
        x = PULLEY_CENTER_B_X - (s - (PULLEY_STRAIGHT_LENGTH + half_circ))
        y = 2.0 * PULLEY_RADIUS
        angle = 180.0
    else:
        theta = math.pi / 2.0 + (s - (2.0 * PULLEY_STRAIGHT_LENGTH + half_circ)) / PULLEY_RADIUS
        x = PULLEY_CENTER_A_X + PULLEY_RADIUS * math.cos(theta)
        y = PULLEY_RADIUS + PULLEY_RADIUS * math.sin(theta)
        angle = math.degrees(theta) + 90.0

    return x, y, angle


def compute_tread_transforms(phase=0.0):
    """Positions + orientations for every tread link around the stadium loop,
    advanced by arc-length `phase`. tank_motion.py calls this per-frame with
    the vehicle's traveled distance to make the belt roll continuously."""
    positions = []
    orientations = []
    for i in range(NUM_TREAD_LINKS):
        x, y, angle_deg = _loop_point(i * LINK_SPACING + phase)
        positions.append(Gf.Vec3f(x, y, 0.0))
        half_angle = math.radians(angle_deg) / 2.0
        orientations.append(Gf.Quath(math.cos(half_angle), 0.0, 0.0, math.sin(half_angle)))
    return Vt.Vec3fArray(positions), Vt.QuathArray(orientations)


def _set_color(prim, color):
    UsdGeom.Gprim(prim).CreateDisplayColorAttr(Vt.Vec3fArray([Gf.Vec3f(*color)]))


if __name__ == "__main__":
    METAL_DARK = (0.32, 0.33, 0.34)
    RUBBER_STEEL = (0.09, 0.09, 0.10)

    # -------------------------------------------------------
    # PART 1: Generate the standalone Tread Link asset
    # -------------------------------------------------------
    link_stage = Usd.Stage.CreateNew("out/tread_link.usda")
    UsdGeom.SetStageUpAxis(link_stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(link_stage, 1.0)

    link_root = UsdGeom.Xform.Define(link_stage, "/TreadLink")
    link_stage.SetDefaultPrim(link_root.GetPrim())

    link_cube = UsdGeom.Cube.Define(link_stage, "/TreadLink/Mesh")
    # Local Z (this scale's 3rd component) becomes the lateral (world X) width once the
    # whole /Track asset is yawed 90 degrees in the assembly, so keep it close to
    # road_wheel_width below instead of the old 0.8, which dwarfed the wheels and read
    # as oversized comb teeth.
    UsdGeom.XformCommonAPI(link_cube).SetScale(Gf.Vec3f(0.1, 0.05, 0.09))  # Flat plate shape
    _set_color(link_cube.GetPrim(), RUBBER_STEEL)

    # Center guide horn: small raised nub so the link reads as an articulated
    # track shoe instead of a plain flat plate.
    guide_horn = UsdGeom.Cube.Define(link_stage, "/TreadLink/GuideHorn")
    UsdGeom.XformCommonAPI(guide_horn).SetTranslate(Gf.Vec3d(0.0, 0.035, 0.0))
    UsdGeom.XformCommonAPI(guide_horn).SetScale(Gf.Vec3f(0.03, 0.02, 0.03))
    _set_color(guide_horn.GetPrim(), RUBBER_STEEL)

    link_stage.GetRootLayer().Save()

    # -------------------------------------------------------
    # PART 2: Build the Track Stage using PointInstancer
    # -------------------------------------------------------
    track_stage = Usd.Stage.CreateNew("out/track.usda")
    UsdGeom.SetStageUpAxis(track_stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(track_stage, 1.0)

    track_root = UsdGeom.Xform.Define(track_stage, "/Track")
    track_stage.SetDefaultPrim(track_root.GetPrim())

    instancer = UsdGeom.PointInstancer.Define(track_stage, "/Track/Instancer")

    proto_prim = track_stage.DefinePrim("/Track/Instancer/Prototypes/LinkProto")
    proto_prim.GetReferences().AddReference("tread_link.usda")
    instancer.GetPrototypesRel().SetTargets([proto_prim.GetPath()])

    positions, orientations = compute_tread_transforms(phase=0.0)
    proto_indices = Vt.IntArray([0] * NUM_TREAD_LINKS)

    instancer.GetPositionsAttr().Set(positions)
    instancer.GetOrientationsAttr().Set(orientations)
    instancer.GetProtoIndicesAttr().Set(proto_indices)

    # -------------------------------------------------------
    # PART 3: Road wheels between the pulleys, plus a rear drive sprocket and
    # front idler wheel closing out the stadium loop the treads trace above.
    # -------------------------------------------------------
    wheels_root = UsdGeom.Xform.Define(track_stage, "/Track/RoadWheels")

    for i in range(NUM_ROAD_WHEELS):
        wheel = UsdGeom.Cylinder.Define(track_stage, f"/Track/RoadWheels/Wheel_{i}")
        wheel.GetRadiusAttr().Set(ROAD_WHEEL_RADIUS)
        wheel.GetHeightAttr().Set(0.15)
        wheel.GetAxisAttr().Set(UsdGeom.Tokens.z)  # wheel disc rolls along the track's X run
        x_pos = WHEEL_RUN_START + i * WHEEL_SPACING
        UsdGeom.XformCommonAPI(wheel).SetTranslate(Gf.Vec3d(x_pos, ROAD_WHEEL_RADIUS, 0.0))
        _set_color(wheel.GetPrim(), RUBBER_STEEL)

    sprocket = UsdGeom.Cylinder.Define(track_stage, "/Track/RoadWheels/DriveSprocket")
    sprocket.GetRadiusAttr().Set(PULLEY_RADIUS)
    sprocket.GetHeightAttr().Set(0.15)
    sprocket.GetAxisAttr().Set(UsdGeom.Tokens.z)
    UsdGeom.XformCommonAPI(sprocket).SetTranslate(Gf.Vec3d(PULLEY_CENTER_A_X, PULLEY_RADIUS, 0.0))
    _set_color(sprocket.GetPrim(), METAL_DARK)

    idler = UsdGeom.Cylinder.Define(track_stage, "/Track/RoadWheels/IdlerWheel")
    idler.GetRadiusAttr().Set(PULLEY_RADIUS)
    idler.GetHeightAttr().Set(0.15)
    idler.GetAxisAttr().Set(UsdGeom.Tokens.z)
    UsdGeom.XformCommonAPI(idler).SetTranslate(Gf.Vec3d(PULLEY_CENTER_B_X, PULLEY_RADIUS, 0.0))
    _set_color(idler.GetPrim(), METAL_DARK)

    track_stage.GetRootLayer().Save()
    print("Successfully generated out/tread_link.usda and out/track.usda")

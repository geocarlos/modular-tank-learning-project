import math

from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, Vt

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


_material_cache = {}


def _get_material(stage, color):
    """One UsdPreviewSurface material per unique color per stage, shared across
    prims, so displayColor also renders in tools (e.g. Blender) that only shade
    from bound materials and ignore the bare displayColor primvar. Keyed by
    stage too: this module authors both tread_link.usda and track.usda, two
    separate stages, in the same process."""
    key = (id(stage), color)
    if key not in _material_cache:
        name = "Mat_{:02x}{:02x}{:02x}".format(*(round(c * 255) for c in color))
        mat_path = f"/{stage.GetDefaultPrim().GetName()}/Materials/{name}"
        material = UsdShade.Material.Define(stage, mat_path)
        shader = UsdShade.Shader.Define(stage, f"{mat_path}/PreviewSurface")
        shader.CreateIdAttr("UsdPreviewSurface")
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
        shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
        material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
        _material_cache[key] = material
    return _material_cache[key]


def _set_color(prim, color):
    UsdGeom.Gprim(prim).CreateDisplayColorAttr(Vt.Vec3fArray([Gf.Vec3f(*color)]))
    UsdShade.MaterialBindingAPI.Apply(prim).Bind(_get_material(prim.GetStage(), color))


def compute_flat_face_normals(points, face_vertex_counts, face_vertex_indices):
    """One normal per face, so hard-surface parts shade as flat facets instead
    of Hydra's default smooth per-vertex normals blending them into a rounded,
    softened look."""
    normals = []
    idx = 0
    for count in face_vertex_counts:
        i0, i1, i2 = face_vertex_indices[idx], face_vertex_indices[idx + 1], face_vertex_indices[idx + 2]
        edge1 = points[i1] - points[i0]
        edge2 = points[i2] - points[i0]
        normal = Gf.Cross(edge1, edge2)
        length = normal.GetLength()
        normals.append(normal / length if length > 1e-8 else normal)
        idx += count
    return normals


def _make_mesh(stage, path, points, face_vertex_counts, face_vertex_indices):
    points_array = Vt.Vec3fArray(points)
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr(points_array)
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray(face_vertex_counts))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(face_vertex_indices))
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)  # keep flat facets
    mesh.CreateDoubleSidedAttr(True)  # tolerate any inconsistent hand-authored winding
    mesh.CreateExtentAttr(UsdGeom.PointBased.ComputeExtent(points_array))
    mesh.CreateNormalsAttr(
        Vt.Vec3fArray(compute_flat_face_normals(points, face_vertex_counts, face_vertex_indices))
    )
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.uniform)
    return mesh


def _make_box_mesh(stage, path, half_extents):
    """An explicit box Mesh, in place of UsdGeom.Cube -- some consumers (e.g.
    Blender's USD importer) don't apply bound materials to implicit Gprim
    shapes like Cube/Cylinder, only to real Mesh prims."""
    hx, hy, hz = half_extents
    points = [
        Gf.Vec3f(-hx, -hy, -hz), Gf.Vec3f(hx, -hy, -hz),
        Gf.Vec3f(hx, hy, -hz), Gf.Vec3f(-hx, hy, -hz),
        Gf.Vec3f(-hx, -hy, hz), Gf.Vec3f(hx, -hy, hz),
        Gf.Vec3f(hx, hy, hz), Gf.Vec3f(-hx, hy, hz),
    ]
    face_vertex_counts = [4, 4, 4, 4, 4, 4]
    face_vertex_indices = [
        0, 1, 2, 3,  # -Z
        5, 4, 7, 6,  # +Z
        4, 0, 3, 7,  # -X
        1, 5, 6, 2,  # +X
        4, 5, 1, 0,  # -Y
        3, 2, 6, 7,  # +Y
    ]
    return _make_mesh(stage, path, points, face_vertex_counts, face_vertex_indices)


def _make_cylinder_mesh(stage, path, radius, height, axis, sides=16):
    """An explicit tessellated cylinder Mesh, in place of UsdGeom.Cylinder --
    see _make_box_mesh for why. `sides` trades roundness for vertex count; 16
    reads as round at this asset's scale while keeping flat-shaded facets
    consistent with the rest of the tank."""
    half_h = height / 2.0
    points = []
    for ring_y in (-half_h, half_h):
        for i in range(sides):
            angle = 2.0 * math.pi * i / sides
            cx = radius * math.cos(angle)
            cz = radius * math.sin(angle)
            if axis == "X":
                points.append(Gf.Vec3f(ring_y, cx, cz))
            elif axis == "Z":
                points.append(Gf.Vec3f(cx, cz, ring_y))
            else:  # "Y"
                points.append(Gf.Vec3f(cx, ring_y, cz))
    # points[0:sides] = bottom ring, points[sides:2*sides] = top ring
    face_vertex_counts = [sides, sides] + [4] * sides
    face_vertex_indices = list(reversed(range(sides))) + list(range(sides, 2 * sides))
    for i in range(sides):
        j = (i + 1) % sides
        face_vertex_indices.extend([i, j, sides + j, sides + i])
    return _make_mesh(stage, path, points, face_vertex_counts, face_vertex_indices)


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

    # Local Z (this half-extent's 3rd component) becomes the lateral (world X) width once the
    # whole /Track asset is yawed 90 degrees in the assembly, so keep it close to
    # road_wheel_width below instead of the old 0.8, which dwarfed the wheels and read
    # as oversized comb teeth.
    link_cube = _make_box_mesh(link_stage, "/TreadLink/Mesh", (0.1, 0.05, 0.09))  # Flat plate shape
    _set_color(link_cube.GetPrim(), RUBBER_STEEL)

    # Center guide horn: small raised nub so the link reads as an articulated
    # track shoe instead of a plain flat plate.
    guide_horn = _make_box_mesh(link_stage, "/TreadLink/GuideHorn", (0.03, 0.02, 0.03))
    UsdGeom.XformCommonAPI(guide_horn).SetTranslate(Gf.Vec3d(0.0, 0.035, 0.0))
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
    # Marks the prototype's subtree as a single instanceable unit. Without this,
    # Blender's PointInstancer import leaves the geometry-nodes "Collection Info"
    # node with no collection to instance, so the tread links import as empty
    # placeholders and never render.
    proto_prim.SetInstanceable(True)
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
        # wheel disc rolls along the track's X run
        wheel = _make_cylinder_mesh(
            track_stage, f"/Track/RoadWheels/Wheel_{i}", radius=ROAD_WHEEL_RADIUS, height=0.15, axis="Z"
        )
        x_pos = WHEEL_RUN_START + i * WHEEL_SPACING
        UsdGeom.XformCommonAPI(wheel).SetTranslate(Gf.Vec3d(x_pos, ROAD_WHEEL_RADIUS, 0.0))
        _set_color(wheel.GetPrim(), RUBBER_STEEL)

    sprocket = _make_cylinder_mesh(
        track_stage, "/Track/RoadWheels/DriveSprocket", radius=PULLEY_RADIUS, height=0.15, axis="Z"
    )
    UsdGeom.XformCommonAPI(sprocket).SetTranslate(Gf.Vec3d(PULLEY_CENTER_A_X, PULLEY_RADIUS, 0.0))
    _set_color(sprocket.GetPrim(), METAL_DARK)

    idler = _make_cylinder_mesh(
        track_stage, "/Track/RoadWheels/IdlerWheel", radius=PULLEY_RADIUS, height=0.15, axis="Z"
    )
    UsdGeom.XformCommonAPI(idler).SetTranslate(Gf.Vec3d(PULLEY_CENTER_B_X, PULLEY_RADIUS, 0.0))
    _set_color(idler.GetPrim(), METAL_DARK)

    track_stage.GetRootLayer().Save()
    print("Successfully generated out/tread_link.usda and out/track.usda")

import math

from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, Vt

# 1. Initialize Stage and Set Global Metadata
stage = Usd.Stage.CreateNew("out/chassis.usda")
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)

# 2. Define Root Xform Prim for the Asset
chassis_root = UsdGeom.Xform.Define(stage, "/Chassis")
stage.SetDefaultPrim(chassis_root.GetPrim())


def compute_flat_face_normals(points, face_vertex_counts, face_vertex_indices):
    """One normal per face, so hard-surface armor plates shade as flat facets
    instead of Hydra's default smooth per-vertex normals blending them into a
    rounded, softened look."""
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


def _make_mesh(path, points, face_vertex_counts, face_vertex_indices):
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


def _make_box_mesh(path, half_extents):
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
    return _make_mesh(path, points, face_vertex_counts, face_vertex_indices)


def _make_cylinder_mesh(path, radius, height, axis, sides=16):
    """An explicit tessellated cylinder Mesh, in place of UsdGeom.Cylinder --
    see _make_box_mesh for why. `sides` trades roundness for vertex count;
    16 reads as round at this asset's scale while keeping flat-shaded facets
    consistent with the rest of the hull."""
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
    return _make_mesh(path, points, face_vertex_counts, face_vertex_indices)


# 3. Build the hull as a custom Mesh: a pentagonal profile extruded across the
#    width, giving a sloped front glacis plate and an angled rear deck/armor
#    plate instead of a plain box (Length 4m, Height 1m, Width 2.5m).
#
#    Profile walked front-to-back in the Y-Z plane:
#      rear-bottom -> front-bottom -> front-glacis-top -> rear-deck-top -> rear-armor-top
half_width = 1.25
profile = [
    Gf.Vec2f(-2.00, 0.00),  # 0: rear bottom (vertical rear plate)
    Gf.Vec2f(2.00, 0.00),   # 1: front bottom (flat belly)
    Gf.Vec2f(1.20, 1.00),   # 2: front glacis top (sloped front armor)
    Gf.Vec2f(-1.00, 1.00),  # 3: rear deck top (flat engine deck)
    Gf.Vec2f(-2.00, 0.40),  # 4: rear armor top (angled rear armor)
]
n = len(profile)

hull_points = []
for x in (-half_width, half_width):
    for z, y in profile:
        hull_points.append(Gf.Vec3f(x, y, z))
# hull_points[0:n]   = left side  (x = -half_width)
# hull_points[n:2*n] = right side (x = +half_width)

hull_face_vertex_counts = []
hull_face_vertex_indices = []

# Left end cap (winds opposite the right cap so it faces outward, -X)
hull_face_vertex_counts.append(n)
hull_face_vertex_indices.extend(reversed(range(n)))

# Right end cap (faces outward, +X)
hull_face_vertex_counts.append(n)
hull_face_vertex_indices.extend(range(n, 2 * n))

# Side plates connecting the two profiles
for i in range(n):
    j = (i + 1) % n
    hull_face_vertex_counts.append(4)
    hull_face_vertex_indices.extend([i, j, n + j, n + i])

body_mesh = _make_mesh("/Chassis/Body", hull_points, hull_face_vertex_counts, hull_face_vertex_indices)

OLIVE_DRAB = (0.23, 0.27, 0.15)
DARK_METAL = (0.08, 0.08, 0.09)

_material_cache = {}


def _get_material(stage, color):
    """One UsdPreviewSurface material per unique color per stage, shared across
    prims, so displayColor also renders in tools (e.g. Blender) that only shade
    from bound materials and ignore the bare displayColor primvar."""
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


_set_color(body_mesh.GetPrim(), OLIVE_DRAB)


# 4. Hull details: headlights, driver's hatch, exhaust pipes, tow hooks and
#    fenders, so the hull reads as more than a bare armored box.
details_root = UsdGeom.Xform.Define(stage, "/Chassis/Details")

# Headlights: dark housing box + amber lens cylinder, one per side of the glacis.
for side in (-1.0, 1.0):
    x = side * (half_width - 0.15)
    housing = _make_box_mesh(
        f"/Chassis/Details/HeadlightHousing_{'L' if side < 0 else 'R'}", (0.06, 0.06, 0.03)
    )
    UsdGeom.XformCommonAPI(housing).SetTranslate(Gf.Vec3d(x, 0.75, 1.55))
    _set_color(housing.GetPrim(), DARK_METAL)

    lens = _make_cylinder_mesh(
        f"/Chassis/Details/HeadlightLens_{'L' if side < 0 else 'R'}",
        radius=0.05, height=0.02, axis="Z",
    )
    UsdGeom.XformCommonAPI(lens).SetTranslate(Gf.Vec3d(x, 0.75, 1.62))
    _set_color(lens.GetPrim(), (0.85, 0.72, 0.32))

# Driver's hatch: raised disc on the front of the flat top deck.
driver_hatch = _make_cylinder_mesh(
    "/Chassis/Details/DriverHatch", radius=0.25, height=0.06, axis="Y"
)
UsdGeom.XformCommonAPI(driver_hatch).SetTranslate(Gf.Vec3d(0.0, 1.03, 0.8))
_set_color(driver_hatch.GetPrim(), (0.19, 0.22, 0.13))

# Exhaust pipes: short vertical cylinders on the rear deck, one per side.
for side in (-1.0, 1.0):
    x = side * 1.0
    exhaust = _make_cylinder_mesh(
        f"/Chassis/Details/Exhaust_{'L' if side < 0 else 'R'}", radius=0.08, height=0.3, axis="Y"
    )
    UsdGeom.XformCommonAPI(exhaust).SetTranslate(Gf.Vec3d(x, 1.05, -1.5))
    _set_color(exhaust.GetPrim(), (0.12, 0.10, 0.09))

# Tow hooks: small blocks at the rear-bottom corners.
for side in (-1.0, 1.0):
    x = side * 0.9
    hook = _make_box_mesh(
        f"/Chassis/Details/TowHook_{'L' if side < 0 else 'R'}", (0.08, 0.08, 0.05)
    )
    UsdGeom.XformCommonAPI(hook).SetTranslate(Gf.Vec3d(x, 0.12, -2.05))
    _set_color(hook.GetPrim(), DARK_METAL)

# Fenders: thin plates over each track run, outboard of the hull sides.
for side in (-1.0, 1.0):
    x = side * (half_width + 0.35)
    fender = _make_box_mesh(
        f"/Chassis/Details/Fender_{'L' if side < 0 else 'R'}", (0.25, 0.02, 1.9)
    )
    UsdGeom.XformCommonAPI(fender).SetTranslate(Gf.Vec3d(x, 0.65, 0.0))
    _set_color(fender.GetPrim(), OLIVE_DRAB)

# 5. Write Stage to Disk
stage.GetRootLayer().Save()
print("Successfully generated out/chassis.usda")

from pxr import Gf, Usd, UsdGeom, Vt

# 1. Initialize Stage and Set Global Metadata
stage = Usd.Stage.CreateNew("out/chassis.usda")
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)

# 2. Define Root Xform Prim for the Asset
chassis_root = UsdGeom.Xform.Define(stage, "/Chassis")
stage.SetDefaultPrim(chassis_root.GetPrim())

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

points = []
for x in (-half_width, half_width):
    for z, y in profile:
        points.append(Gf.Vec3f(x, y, z))
# points[0:n]   = left side  (x = -half_width)
# points[n:2*n] = right side (x = +half_width)

face_vertex_counts = []
face_vertex_indices = []

# Left end cap (winds opposite the right cap so it faces outward, -X)
face_vertex_counts.append(n)
face_vertex_indices.extend(reversed(range(n)))

# Right end cap (faces outward, +X)
face_vertex_counts.append(n)
face_vertex_indices.extend(range(n, 2 * n))

# Side plates connecting the two profiles
for i in range(n):
    j = (i + 1) % n
    face_vertex_counts.append(4)
    face_vertex_indices.extend([i, j, n + j, n + i])

points_array = Vt.Vec3fArray(points)


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


body_mesh = UsdGeom.Mesh.Define(stage, "/Chassis/Body")
body_mesh.CreatePointsAttr(points_array)
body_mesh.CreateFaceVertexCountsAttr(Vt.IntArray(face_vertex_counts))
body_mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(face_vertex_indices))
body_mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)  # keep flat armor facets
body_mesh.CreateDoubleSidedAttr(True)  # tolerate any inconsistent hand-authored winding
body_mesh.CreateExtentAttr(UsdGeom.PointBased.ComputeExtent(points_array))
body_mesh.CreateNormalsAttr(
    Vt.Vec3fArray(compute_flat_face_normals(points, face_vertex_counts, face_vertex_indices))
)
body_mesh.SetNormalsInterpolation(UsdGeom.Tokens.uniform)

OLIVE_DRAB = (0.23, 0.27, 0.15)
DARK_METAL = (0.08, 0.08, 0.09)
body_mesh.CreateDisplayColorAttr(Vt.Vec3fArray([Gf.Vec3f(*OLIVE_DRAB)]))


def _set_color(prim, color):
    UsdGeom.Gprim(prim).CreateDisplayColorAttr(Vt.Vec3fArray([Gf.Vec3f(*color)]))


# 4. Hull details: headlights, driver's hatch, exhaust pipes, tow hooks and
#    fenders, so the hull reads as more than a bare armored box.
details_root = UsdGeom.Xform.Define(stage, "/Chassis/Details")

# Headlights: dark housing cube + amber lens cylinder, one per side of the glacis.
for side in (-1.0, 1.0):
    x = side * (half_width - 0.15)
    housing = UsdGeom.Cube.Define(stage, f"/Chassis/Details/HeadlightHousing_{'L' if side < 0 else 'R'}")
    UsdGeom.XformCommonAPI(housing).SetTranslate(Gf.Vec3d(x, 0.75, 1.55))
    UsdGeom.XformCommonAPI(housing).SetScale(Gf.Vec3f(0.06, 0.06, 0.03))
    _set_color(housing.GetPrim(), DARK_METAL)

    lens = UsdGeom.Cylinder.Define(stage, f"/Chassis/Details/HeadlightLens_{'L' if side < 0 else 'R'}")
    lens.GetRadiusAttr().Set(0.05)
    lens.GetHeightAttr().Set(0.02)
    lens.GetAxisAttr().Set(UsdGeom.Tokens.z)
    UsdGeom.XformCommonAPI(lens).SetTranslate(Gf.Vec3d(x, 0.75, 1.62))
    _set_color(lens.GetPrim(), (0.85, 0.72, 0.32))

# Driver's hatch: raised disc on the front of the flat top deck.
driver_hatch = UsdGeom.Cylinder.Define(stage, "/Chassis/Details/DriverHatch")
driver_hatch.GetRadiusAttr().Set(0.25)
driver_hatch.GetHeightAttr().Set(0.06)
driver_hatch.GetAxisAttr().Set(UsdGeom.Tokens.y)
UsdGeom.XformCommonAPI(driver_hatch).SetTranslate(Gf.Vec3d(0.0, 1.03, 0.8))
_set_color(driver_hatch.GetPrim(), (0.19, 0.22, 0.13))

# Exhaust pipes: short vertical cylinders on the rear deck, one per side.
for side in (-1.0, 1.0):
    x = side * 1.0
    exhaust = UsdGeom.Cylinder.Define(stage, f"/Chassis/Details/Exhaust_{'L' if side < 0 else 'R'}")
    exhaust.GetRadiusAttr().Set(0.08)
    exhaust.GetHeightAttr().Set(0.3)
    exhaust.GetAxisAttr().Set(UsdGeom.Tokens.y)
    UsdGeom.XformCommonAPI(exhaust).SetTranslate(Gf.Vec3d(x, 1.05, -1.5))
    _set_color(exhaust.GetPrim(), (0.12, 0.10, 0.09))

# Tow hooks: small blocks at the rear-bottom corners.
for side in (-1.0, 1.0):
    x = side * 0.9
    hook = UsdGeom.Cube.Define(stage, f"/Chassis/Details/TowHook_{'L' if side < 0 else 'R'}")
    UsdGeom.XformCommonAPI(hook).SetTranslate(Gf.Vec3d(x, 0.12, -2.05))
    UsdGeom.XformCommonAPI(hook).SetScale(Gf.Vec3f(0.08, 0.08, 0.05))
    _set_color(hook.GetPrim(), DARK_METAL)

# Fenders: thin plates over each track run, outboard of the hull sides.
for side in (-1.0, 1.0):
    x = side * (half_width + 0.35)
    fender = UsdGeom.Cube.Define(stage, f"/Chassis/Details/Fender_{'L' if side < 0 else 'R'}")
    UsdGeom.XformCommonAPI(fender).SetTranslate(Gf.Vec3d(x, 0.65, 0.0))
    UsdGeom.XformCommonAPI(fender).SetScale(Gf.Vec3f(0.25, 0.02, 1.9))
    _set_color(fender.GetPrim(), OLIVE_DRAB)

# 5. Write Stage to Disk
stage.GetRootLayer().Save()
print("Successfully generated out/chassis.usda")

import math

from pxr import Gf, Usd, UsdGeom, Vt

# 1. Initialize Stage
stage = Usd.Stage.CreateNew("out/turret.usda")
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)

# 2. Define Root Xform and Main Turret Base
turret_root = UsdGeom.Xform.Define(stage, "/Turret")
stage.SetDefaultPrim(turret_root.GetPrim())

# 3. Build the turret housing as a faceted Mesh: an 8-sided frustum that
#    tapers inward toward the top for an angled, armored silhouette
#    (replaces the plain UsdGeom.Cylinder).
sides = 8
# Sized well under the 2.5m hull width (half_width=1.25 in chassis.py) so the
# turret reads as a turret sitting on the hull, not a drum spanning it.
bottom_radius = 0.75
top_radius = 0.55
housing_height = 0.6

points = []
for radius, y in ((bottom_radius, 0.0), (top_radius, housing_height)):
    for i in range(sides):
        angle = 2.0 * math.pi * i / sides
        points.append(Gf.Vec3f(radius * math.cos(angle), y, radius * math.sin(angle)))
# points[0:sides]      = bottom ring
# points[sides:2*sides] = top ring

face_vertex_counts = []
face_vertex_indices = []

# Bottom cap (faces outward, -Y)
face_vertex_counts.append(sides)
face_vertex_indices.extend(reversed(range(sides)))

# Top cap (faces outward, +Y)
face_vertex_counts.append(sides)
face_vertex_indices.extend(range(sides, 2 * sides))

# Angled side plates connecting the two rings
for i in range(sides):
    j = (i + 1) % sides
    face_vertex_counts.append(4)
    face_vertex_indices.extend([i, j, sides + j, sides + i])

points_array = Vt.Vec3fArray(points)


def compute_flat_face_normals(points, face_vertex_counts, face_vertex_indices):
    """One normal per face, so the octagon shades as flat armor facets instead
    of Hydra's default smooth per-vertex normals blending it into a round dome."""
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


base_mesh = UsdGeom.Mesh.Define(stage, "/Turret/Base")
base_mesh.CreatePointsAttr(points_array)
base_mesh.CreateFaceVertexCountsAttr(Vt.IntArray(face_vertex_counts))
base_mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(face_vertex_indices))
base_mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)  # keep flat armor facets
base_mesh.CreateDoubleSidedAttr(True)
base_mesh.CreateExtentAttr(UsdGeom.PointBased.ComputeExtent(points_array))
base_mesh.CreateNormalsAttr(
    Vt.Vec3fArray(compute_flat_face_normals(points, face_vertex_counts, face_vertex_indices))
)
base_mesh.SetNormalsInterpolation(UsdGeom.Tokens.uniform)

OLIVE_DRAB = (0.23, 0.27, 0.15)
GUNMETAL = (0.15, 0.15, 0.16)
DARK_METAL = (0.08, 0.08, 0.09)
base_mesh.CreateDisplayColorAttr(Vt.Vec3fArray([Gf.Vec3f(*OLIVE_DRAB)]))


def _set_color(prim, color):
    UsdGeom.Gprim(prim).CreateDisplayColorAttr(Vt.Vec3fArray([Gf.Vec3f(*color)]))


# 3b. Common turret details (outside any variant, so both weapon loadouts get
# them): commander's hatch, antenna mount, and smoke grenade launchers.
commander_hatch = UsdGeom.Cylinder.Define(stage, "/Turret/CommanderHatch")
commander_hatch.GetRadiusAttr().Set(0.18)
commander_hatch.GetHeightAttr().Set(0.05)
commander_hatch.GetAxisAttr().Set(UsdGeom.Tokens.y)
UsdGeom.XformCommonAPI(commander_hatch).SetTranslate(Gf.Vec3d(-0.25, housing_height + 0.02, -0.15))
_set_color(commander_hatch.GetPrim(), OLIVE_DRAB)

antenna = UsdGeom.Cylinder.Define(stage, "/Turret/Antenna")
antenna.GetRadiusAttr().Set(0.015)
antenna.GetHeightAttr().Set(0.9)
antenna.GetAxisAttr().Set(UsdGeom.Tokens.y)
UsdGeom.XformCommonAPI(antenna).SetTranslate(Gf.Vec3d(0.35, housing_height + 0.45, -0.55))
_set_color(antenna.GetPrim(), DARK_METAL)

for side in (-1.0, 1.0):
    for row in range(3):
        launcher = UsdGeom.Cylinder.Define(
            stage, f"/Turret/SmokeLauncher_{'L' if side < 0 else 'R'}_{row}"
        )
        launcher.GetRadiusAttr().Set(0.025)
        launcher.GetHeightAttr().Set(0.18)
        launcher.GetAxisAttr().Set(UsdGeom.Tokens.z)
        UsdGeom.XformCommonAPI(launcher).SetTranslate(
            Gf.Vec3d(side * (0.45 + row * 0.07), housing_height * 0.55, bottom_radius * 0.85)
        )
        _set_color(launcher.GetPrim(), GUNMETAL)

# 4. Create VariantSet on the Turret Root Prim
vset = turret_root.GetPrim().GetVariantSets().AddVariantSet("weaponType")


def _build_barrel(root_path, xy_translate,
                   mantlet_radius, mantlet_height, mantlet_center,
                   tube_radius, tube_height, tube_center,
                   brake_radius, brake_height, brake_center):
    """Author a Mantlet -> Tube -> MuzzleBrake cylinder stack under an Xform root."""
    barrel_xform = UsdGeom.Xform.Define(stage, root_path)
    UsdGeom.XformCommonAPI(barrel_xform).SetTranslate(xy_translate)

    mantlet = UsdGeom.Cylinder.Define(stage, root_path + "/Mantlet")
    mantlet.GetRadiusAttr().Set(mantlet_radius)
    mantlet.GetHeightAttr().Set(mantlet_height)
    mantlet.GetAxisAttr().Set(UsdGeom.Tokens.z)
    UsdGeom.XformCommonAPI(mantlet).SetTranslate(Gf.Vec3d(0.0, 0.0, mantlet_center))
    _set_color(mantlet.GetPrim(), OLIVE_DRAB)

    tube = UsdGeom.Cylinder.Define(stage, root_path + "/Tube")
    tube.GetRadiusAttr().Set(tube_radius)
    tube.GetHeightAttr().Set(tube_height)
    tube.GetAxisAttr().Set(UsdGeom.Tokens.z)
    UsdGeom.XformCommonAPI(tube).SetTranslate(Gf.Vec3d(0.0, 0.0, tube_center))
    _set_color(tube.GetPrim(), GUNMETAL)

    muzzle_brake = UsdGeom.Cylinder.Define(stage, root_path + "/MuzzleBrake")
    muzzle_brake.GetRadiusAttr().Set(brake_radius)
    muzzle_brake.GetHeightAttr().Set(brake_height)
    muzzle_brake.GetAxisAttr().Set(UsdGeom.Tokens.z)
    UsdGeom.XformCommonAPI(muzzle_brake).SetTranslate(Gf.Vec3d(0.0, 0.0, brake_center))
    _set_color(muzzle_brake.GetPrim(), DARK_METAL)


# 5. Author Variant 1: Single Cannon
# Barrel z-spans are contiguous and picked so the mantlet meets the turret's
# front face at roughly z=bottom_radius, instead of floating inside/outside it.
vset.AddVariant("SingleCannon")
vset.SetVariantSelection("SingleCannon")
with vset.GetVariantEditContext():
    _build_barrel(
        "/Turret/Barrel", Gf.Vec3d(0.0, housing_height / 2.0, 0.0),
        mantlet_radius=0.30, mantlet_height=0.4, mantlet_center=0.55,
        tube_radius=0.14, tube_height=1.6, tube_center=1.55,
        brake_radius=0.20, brake_height=0.3, brake_center=2.50,
    )

# 6. Author Variant 2: Dual Autocannon
vset.AddVariant("DualAutocannon")
vset.SetVariantSelection("DualAutocannon")
with vset.GetVariantEditContext():
    _build_barrel(
        "/Turret/BarrelLeft", Gf.Vec3d(-0.28, housing_height / 2.0, 0.0),
        mantlet_radius=0.15, mantlet_height=0.25, mantlet_center=0.475,
        tube_radius=0.07, tube_height=1.3, tube_center=1.25,
        brake_radius=0.11, brake_height=0.2, brake_center=2.00,
    )
    _build_barrel(
        "/Turret/BarrelRight", Gf.Vec3d(0.28, housing_height / 2.0, 0.0),
        mantlet_radius=0.15, mantlet_height=0.25, mantlet_center=0.475,
        tube_radius=0.07, tube_height=1.3, tube_center=1.25,
        brake_radius=0.11, brake_height=0.2, brake_center=2.00,
    )

# 7. Set Default Selection back to SingleCannon
vset.SetVariantSelection("SingleCannon")

stage.GetRootLayer().Save()
print("Successfully generated out/turret.usda")

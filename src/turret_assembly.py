import math

from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, Vt

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


def _make_mesh(path, points, face_vertex_counts, face_vertex_indices):
    points_array = Vt.Vec3fArray(points)
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr(points_array)
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray(face_vertex_counts))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(face_vertex_indices))
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)  # keep flat armor facets
    mesh.CreateDoubleSidedAttr(True)  # tolerate any inconsistent hand-authored winding
    mesh.CreateExtentAttr(UsdGeom.PointBased.ComputeExtent(points_array))
    mesh.CreateNormalsAttr(
        Vt.Vec3fArray(compute_flat_face_normals(points, face_vertex_counts, face_vertex_indices))
    )
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.uniform)
    return mesh


def _make_cylinder_mesh(path, radius, height, axis, sides=16):
    """An explicit tessellated cylinder Mesh, in place of UsdGeom.Cylinder --
    some consumers (e.g. Blender's USD importer) don't apply bound materials
    to implicit Gprim shapes like Cylinder, only to real Mesh prims. `sides`
    trades roundness for vertex count; 16 reads as round at this asset's
    scale while keeping flat-shaded facets consistent with the housing."""
    half_h = height / 2.0
    cyl_points = []
    for ring_y in (-half_h, half_h):
        for i in range(sides):
            angle = 2.0 * math.pi * i / sides
            cx = radius * math.cos(angle)
            cz = radius * math.sin(angle)
            if axis == "X":
                cyl_points.append(Gf.Vec3f(ring_y, cx, cz))
            elif axis == "Z":
                cyl_points.append(Gf.Vec3f(cx, cz, ring_y))
            else:  # "Y"
                cyl_points.append(Gf.Vec3f(cx, ring_y, cz))
    # cyl_points[0:sides] = bottom ring, cyl_points[sides:2*sides] = top ring
    cyl_face_vertex_counts = [sides, sides] + [4] * sides
    cyl_face_vertex_indices = list(reversed(range(sides))) + list(range(sides, 2 * sides))
    for i in range(sides):
        j = (i + 1) % sides
        cyl_face_vertex_indices.extend([i, j, sides + j, sides + i])
    return _make_mesh(path, cyl_points, cyl_face_vertex_counts, cyl_face_vertex_indices)


base_mesh = _make_mesh("/Turret/Base", points, face_vertex_counts, face_vertex_indices)

OLIVE_DRAB = (0.23, 0.27, 0.15)
GUNMETAL = (0.15, 0.15, 0.16)
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


_set_color(base_mesh.GetPrim(), OLIVE_DRAB)


# 3b. Common turret details (outside any variant, so both weapon loadouts get
# them): commander's hatch, antenna mount, and smoke grenade launchers.
commander_hatch = _make_cylinder_mesh("/Turret/CommanderHatch", radius=0.18, height=0.05, axis="Y")
UsdGeom.XformCommonAPI(commander_hatch).SetTranslate(Gf.Vec3d(-0.25, housing_height + 0.02, -0.15))
_set_color(commander_hatch.GetPrim(), OLIVE_DRAB)

antenna = _make_cylinder_mesh("/Turret/Antenna", radius=0.015, height=0.9, axis="Y")
UsdGeom.XformCommonAPI(antenna).SetTranslate(Gf.Vec3d(0.35, housing_height + 0.45, -0.55))
_set_color(antenna.GetPrim(), DARK_METAL)

for side in (-1.0, 1.0):
    for row in range(3):
        launcher = _make_cylinder_mesh(
            f"/Turret/SmokeLauncher_{'L' if side < 0 else 'R'}_{row}",
            radius=0.025, height=0.18, axis="Z",
        )
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

    mantlet = _make_cylinder_mesh(root_path + "/Mantlet", radius=mantlet_radius, height=mantlet_height, axis="Z")
    UsdGeom.XformCommonAPI(mantlet).SetTranslate(Gf.Vec3d(0.0, 0.0, mantlet_center))
    _set_color(mantlet.GetPrim(), OLIVE_DRAB)

    tube = _make_cylinder_mesh(root_path + "/Tube", radius=tube_radius, height=tube_height, axis="Z")
    UsdGeom.XformCommonAPI(tube).SetTranslate(Gf.Vec3d(0.0, 0.0, tube_center))
    _set_color(tube.GetPrim(), GUNMETAL)

    muzzle_brake = _make_cylinder_mesh(root_path + "/MuzzleBrake", radius=brake_radius, height=brake_height, axis="Z")
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

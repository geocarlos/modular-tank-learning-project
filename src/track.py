from pxr import Gf, Usd, UsdGeom, Vt

# ---------------------------------------------------------
# PART 1: Generate the standalone Tread Link asset
# ---------------------------------------------------------
link_stage = Usd.Stage.CreateNew("usd/tread_link.usda")
UsdGeom.SetStageUpAxis(link_stage, UsdGeom.Tokens.y)
UsdGeom.SetStageMetersPerUnit(link_stage, 1.0)

link_root = UsdGeom.Xform.Define(link_stage, "/TreadLink")
link_stage.SetDefaultPrim(link_root.GetPrim())

link_cube = UsdGeom.Cube.Define(link_stage, "/TreadLink/Mesh")
UsdGeom.XformCommonAPI(link_cube).SetScale(Gf.Vec3f(0.1, 0.05, 0.4))  # Flat plate shape
link_stage.GetRootLayer().Save()

# ---------------------------------------------------------
# PART 2: Build the Track Stage using PointInstancer
# ---------------------------------------------------------
track_stage = Usd.Stage.CreateNew("usd/track.usda")
UsdGeom.SetStageUpAxis(track_stage, UsdGeom.Tokens.y)
UsdGeom.SetStageMetersPerUnit(track_stage, 1.0)

# Create Root Transform and PointInstancer Prim
track_root = UsdGeom.Xform.Define(track_stage, "/Track")
track_stage.SetDefaultPrim(track_root.GetPrim())

instancer = UsdGeom.PointInstancer.Define(track_stage, "/Track/Instancer")

# Create local Prototype shell and reference the Tread Link asset into it
proto_prim = track_stage.DefinePrim("/Track/Instancer/Prototypes/LinkProto")
proto_prim.GetReferences().AddReference("tread_link.usda")

# Connect the Prototype target to the Instancer
instancer.GetPrototypesRel().SetTargets([proto_prim.GetPath()])

# Generate positions for a line of treads (extend this math to a loop later)
num_treads = 12
positions = Vt.Vec3fArray([Gf.Vec3f(i * 0.25, 0.0, 0.0) for i in range(num_treads)])
proto_indices = Vt.IntArray([0] * num_treads)  # Index 0 maps to LinkProto

# Assign instance array attributes
instancer.GetPositionsAttr().Set(positions)
instancer.GetProtoIndicesAttr().Set(proto_indices)

track_stage.GetRootLayer().Save()
print("Successfully generated usd/tread_link.usda and usd/track.usda")
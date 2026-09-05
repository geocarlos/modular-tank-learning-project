from pxr import Gf, Usd, UsdGeom

# 1. Initialize Stage
stage = Usd.Stage.CreateNew("out/turret.usda")
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)

# 2. Define Root Xform and Main Turret Base
turret_root = UsdGeom.Xform.Define(stage, "/Turret")
stage.SetDefaultPrim(turret_root.GetPrim())

base_mesh = UsdGeom.Cylinder.Define(stage, "/Turret/Base")
base_mesh.GetHeightAttr().Set(0.8)
base_mesh.GetRadiusAttr().Set(1.2)
UsdGeom.XformCommonAPI(base_mesh).SetTranslate(Gf.Vec3d(0.0, 0.4, 0.0))

# 3. Create VariantSet on the Turret Root Prim
vset = turret_root.GetPrim().GetVariantSets().AddVariantSet("weaponType")

# 4. Author Variant 1: Single Cannon
vset.AddVariant("SingleCannon")
vset.SetVariantSelection("SingleCannon")
with vset.GetVariantEditContext():
    barrel = UsdGeom.Cylinder.Define(stage, "/Turret/Barrel")
    barrel.GetHeightAttr().Set(2.5)
    barrel.GetRadiusAttr().Set(0.15)
    barrel.GetAxisAttr().Set(UsdGeom.Tokens.z)
    UsdGeom.XformCommonAPI(barrel).SetTranslate(Gf.Vec3d(0.0, 0.5, 1.25))

# 5. Author Variant 2: Dual Autocannon
vset.AddVariant("DualAutocannon")
vset.SetVariantSelection("DualAutocannon")
with vset.GetVariantEditContext():
    left_barrel = UsdGeom.Cylinder.Define(stage, "/Turret/BarrelLeft")
    left_barrel.GetHeightAttr().Set(2.0)
    left_barrel.GetRadiusAttr().Set(0.08)
    left_barrel.GetAxisAttr().Set(UsdGeom.Tokens.z)
    UsdGeom.XformCommonAPI(left_barrel).SetTranslate(Gf.Vec3d(-0.4, 0.5, 1.0))

    right_barrel = UsdGeom.Cylinder.Define(stage, "/Turret/BarrelRight")
    right_barrel.GetHeightAttr().Set(2.0)
    right_barrel.GetRadiusAttr().Set(0.08)
    right_barrel.GetAxisAttr().Set(UsdGeom.Tokens.z)
    UsdGeom.XformCommonAPI(right_barrel).SetTranslate(Gf.Vec3d(0.4, 0.5, 1.0))

# 6. Set Default Selection back to SingleCannon
vset.SetVariantSelection("SingleCannon")

stage.GetRootLayer().Save()
print("Successfully generated out/turret.usda")
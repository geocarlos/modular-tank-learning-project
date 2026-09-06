"""Bakes the PointInstancer-based tread links into explicit, per-instance
Xform prims and flattens the whole composition into a single self-contained
file (out/tank_final.usdc).

Why: PointInstancer support is inconsistent across downstream tools (Blender's
importer wires up a geometry-nodes instancer that can fail to link its
prototype collection; simple viewers like usd2gltf/usdz-viewer.net skip
PointInstancer prims entirely). Baking to explicit prims makes the tread
links plain, referenced Xform hierarchies that any USD-consuming tool can
render without special instancing support.
"""

from pathlib import Path

from pxr import Sdf, Usd, UsdGeom

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"
MOTION_LAYER = OUT_DIR / "tank_motion.usda"
EXPORT_LAYER = OUT_DIR / "tank_final.usdc"


def _prototype_asset_layer(proto_prim):
    """The prototype prim (e.g. LinkProto) is marked instanceable, so USD
    hides its actual children behind an opaque, unreferenceable internal
    master (/__Prototype_N). Read the plain asset reference it was authored
    with instead, and reuse that as the source for each baked copy."""
    list_op = proto_prim.GetMetadata("references")
    items = list_op.explicitItems if list_op.isExplicit else (
        list_op.addedItems or list_op.prependedItems
    )
    ref = items[0]
    asset_path = OUT_DIR / ref.assetPath
    layer = Sdf.Layer.FindOrOpen(str(asset_path))
    default_prim_path = Sdf.Path.absoluteRootPath.AppendChild(layer.defaultPrim)
    return layer, default_prim_path


def bake_point_instancer(stage, instancer_prim):
    instancer = UsdGeom.PointInstancer(instancer_prim)

    proto_targets = instancer.GetPrototypesRel().GetForwardedTargets()
    proto_prim = stage.GetPrimAtPath(proto_targets[0])
    source_layer, source_path = _prototype_asset_layer(proto_prim)

    num_instances = len(instancer.GetProtoIndicesAttr().Get())
    parent_path = instancer_prim.GetPath().GetParentPath()
    dest_layer = stage.GetEditTarget().GetLayer()

    # A sibling of the instancer, not a child -- deactivating the instancer
    # below must not also deactivate the baked geometry. Defining this first
    # (via the Stage API, not raw Sdf) also authors "over" specs for every
    # ancestor up to and including parent_path on the session layer, which
    # Sdf.CopySpec below requires to already exist at its destination's parent.
    links_scope = UsdGeom.Scope.Define(stage, parent_path.AppendChild("Links"))

    # Copy the source asset (geometry + its materials) ONCE into a plain,
    # non-instanceable template, then INTERNAL-REFERENCE it per instance below
    # rather than re-running Sdf.CopySpec per instance. A reference is what
    # makes this work correctly: USD's composition remaps relationship
    # targets (e.g. each Mesh's material:binding, which points at a sibling
    # under the template) into every instance's own namespace. A raw
    # Sdf.CopySpec copies such targets verbatim, so duplicating the whole
    # subtree per instance would leave every copy's material binding pointing
    # at the ORIGINAL template path -- dangling everywhere except the first.
    template_path = parent_path.AppendChild("LinkTemplate")
    Sdf.CopySpec(source_layer, source_path, dest_layer, template_path)

    xform_ops = []
    for i in range(num_instances):
        link_path = links_scope.GetPath().AppendChild(f"Link_{i}")
        link_prim = stage.DefinePrim(link_path)
        link_prim.GetReferences().AddInternalReference(template_path)
        xform_ops.append(UsdGeom.Xformable(link_prim).AddTransformOp())

    start = stage.GetStartTimeCode()
    end = stage.GetEndTimeCode()
    for frame in range(int(start), int(end) + 1):
        transforms = instancer.ComputeInstanceTransformsAtTime(frame, frame)
        for op, matrix in zip(xform_ops, transforms):
            op.Set(matrix, Usd.TimeCode(frame))

    # Deactivate the instancer (and its Prototypes/LinkProto child) now that
    # its geometry has been copied out to the sibling Links scope above.
    # A plain visibility=invisible opinion isn't enough: viewers that ignore
    # UsdGeomImageable visibility (e.g. three.js-based tools) would still
    # render the leftover, untransformed prototype at the origin.
    instancer_prim.SetActive(False)


def main():
    stage = Usd.Stage.Open(str(MOTION_LAYER))
    stage.SetEditTarget(Usd.EditTarget(stage.GetSessionLayer()))

    instancer_prims = [
        prim for prim in stage.Traverse() if prim.IsA(UsdGeom.PointInstancer)
    ]
    for prim in instancer_prims:
        bake_point_instancer(stage, prim)

    flat_layer = stage.Flatten()
    flat_layer.Export(str(EXPORT_LAYER))
    print(f"Baked {len(instancer_prims)} point instancer(s) and wrote {EXPORT_LAYER}")


if __name__ == "__main__":
    main()

# Existing-model asset audit and Digital Campus export

The corrected source `CUHK_shaw_science_corrected.blend` remains unchanged. The
previous `public/model` assets remain available as the comparison baseline.

## Baseline measured from the shipped GLBs

| Resource | Bytes | Triangles | Primitive submissions |
| --- | ---: | ---: | ---: |
| terrain.glb | 14,566,228 | 5,269,222 | 2 |
| campus.glb | 20,076,888 | 2,343,302 | 1,387 |
| Total | 34,643,116 | 7,612,524 | 1,389 |

These submissions are for one full unculled color pass. Actual browser draw calls
depend on visibility, shadows and postprocessing; they are not an FPS measurement.
Decoded vertex/index accessors occupy about 202.64 MiB before driver padding,
render targets and CPU copies.

The model covers approximately 2.4 × 2.4 km. There are 369 addressable buildings,
223 campus materials (217 distinct value combinations), zero image textures and
no exported UV sets. Materials use constant PBR base color, roughness and metalness.
There are consequently no PNG/JPEG duplicates or 4K images to recompress into
KTX2. Atlas/KTX2 work is deferred until actual texture maps are introduced.

The 1,374 original trees use eight shared meshes in Blender, but the old export
expanded them into 472,656 triangles. CampusLife restores those exact templates
and transforms as instances. Existing 157 lamps, road/court paint, curbs, goals,
nets, pool lane ropes and turf stripes are retained; they are not recreated.

## Delivered structure

`public/campus/manifest.json` describes:

- Sixteen terrain tiles, preserving every road triangle's covered 8 m block at
  the original 1 m resolution and diagonal. Sports surfaces and the corrected
  Shaw footprint are also protected. Other terrain uses stitched 8 m samples.
- `site.glb`: unchanged road, sport, water, foundation and existing prop geometry.
- `buildings-low.glb`: all original building shells, authored colors and IDs,
  plus original glazing, principal accent panels and tile roof parts. Fine window
  frames are omitted; the existing window geometry is not regenerated. Glazing
  stays in a separate material so distant windows can participate in night lighting.
  Seven authored landmarks and corrected Shaw retain their detailed geometry.
- Twelve spatial building zones, each available as medium and high GLBs.
- `heightfield.json`: 14,641 conservative cell maxima for camera clearance.

| Building LOD | Total triangles across all zones |
| --- | ---: |
| Low, resident at entry | 125,457 |
| Medium, streamed nearby | 397,704 |
| High, streamed close/selected | 818,377 |

The initial terrain/site/building package is **24,059,236 bytes, 4,285,449
triangles and 594 primitive submissions**, before separately loaded tree instances,
campus life, shadows or postprocessing. Full high geometry is not loaded at entry.

The StreamingSystem loads at most two detail files concurrently. Current detail
replaces the corresponding low building nodes; departing zones return to their
low representation after a short grace period and dispose their geometries and
materials. A 20% threshold hysteresis avoids high/medium churn. High quality streams
medium detail within 850 m (five zones), medium quality within 600 m (three zones),
and low quality within 330 m (two zones); low quality never requests high LOD.
The debug distance multiplier is bounded to 0.5–1.5.

`stats.loadedMiB` means compressed GLB payload represented by current scene roots;
it is **not GPU memory**. Renderer geometry buffers and render targets need their
own estimate. Runtime callbacks register and unregister only their passed root;
ray picking must exclude objects with any hidden ancestor.

## Compression choice

All 42 exported terrain/site/building files use `EXT_meshopt_compression` with
float32 positions to retain tiny road offsets. Only normals/colors are quantized.
An identical-topology full-campus comparison measured 20,076,888 bytes / 696 ms
for Draco and 25,229,144 bytes / 194 ms for Meshopt in one Node decode run. Meshopt
is larger on that comparison, but decoded faster; subdivision and LOD reduce the
actual initial download. This is not a browser or device FPS benchmark.

The conversion uses glTF Transform 4.5.0 and meshoptimizer 1.3.0 in isolated build
tooling. Browser decoding uses the existing Three.js 0.185.1 bundled decoder,
which was used again by the validation script. No runtime package was added.
The implementation follows the official [glTF Transform Meshopt documentation](https://gltf-transform.dev/modules/functions/functions/meshopt).

## Reproduce and verify

1. Run Blender in background with `artifacts/cuhk/export_digital_campus.py`.
2. Run Node with `artifacts/cuhk/tools/gltf/build_digital_campus.mjs`.
3. Run Node with `artifacts/cuhk/tools/gltf/validate_digital_campus.mjs`.
4. Run `node --test streaming.test.js` from the web project.

Validation decodes every file, checks all 369 IDs, compares every high building's
bounds with the prior validated GLB, and compares indexed site positions before
and after export. Both track height ranges are zero. Shaw's 117.6 m top and 352
vertices on the 111.6 m main roof remain present even in the initial LOD. The four
streaming checks cover replacement/disposal accounting, stale responses, distance
hysteresis/quality and failure fallback.

Detailed machine-readable results are in `asset_audit.json`,
`blender_structure_audit.json`, `digital_asset_report.json` and
`digital_asset_validation.json` in this folder. Browser visual/FPS validation is
performed by the main integration task.

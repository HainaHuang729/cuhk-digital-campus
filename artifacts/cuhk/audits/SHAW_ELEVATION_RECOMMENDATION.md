# Run Run Shaw Science Building elevation audit

Read-only audit of OSM building 107139044 against cached CEDD 2020 LiDAR-derived 0.5 m DSM and DTM. Local coordinates are EPSG:2326 minus East 839400 / North 831150; all elevations are HKPD meters. No source model, terrain, or GIS data was modified.

## Measured roof anchors

- Main roof slab: **111.60 m HKPD**. 3,574 interior samples in the dominant 111.3–111.9 m plateau have median 111.5989 m and 5th–95th percentiles 111.4654–111.7413 m. A fitted diagnostic plane has 0.085 m RMS residual; this is not a claim of survey accuracy.
- Raised end cores / rooftop plant: model bulk top near **117.6 m HKPD**, with isolated equipment returns up to approximately 120 m.
- No interior DSM sample exceeds 115 m in the middle x=50..110 m: tall blocks belong at the ends, not across the whole roof.
- Western raised return footprint (>115 m): x=26.75..49.75, y=-125.25..-99.75 m.
- Eastern raised return footprint (>115 m): x=111.25..132.25, y=-89.75..-71.25 m.

The current main source model roof is 90.64875 m HKPD, approximately **20.95 m below** the dominant roof slab measured in the DSM.

## Hillside and ground

The original bare-earth DTM upper terrace along the northern and northwestern rear faces is approximately 97.5–97.65 m HKPD. The southern downhill long faces have adjacent DTM medians approximately 76.2 m (eastern wing) and 74.1 m (western wing). The footprint median DTM is 87.48 m and the lower-quartile DTM is 80.80 m. A single lower-quartile ground statistic cannot determine the street-entry elevation of this hillside building.

The latest displayed terrain has a substantial artificial depression along the western uphill face: outside edge 20 median 81.17 m versus original 97.63 m. The eastern uphill face median is 94.50 m versus original 97.49 m. A correction should consider restoring the rear terrace, while protecting the existing road network and junction continuity.

Latest displayed terrain sampled every 0.5 m along the exact footprint boundary has minimum 71.485 m, at x=39.878,y=-122.606 m; p05=74.099 m, median=80.732 m. A solid foundation extending to 71.0 m HKPD avoids a visible gap under the existing display terrain, although retaining walls/pier geometry would better represent the hillside than one unbroken deep wall.

## Modeling limits

The roof heights are strongly supported by spatially coherent DSM returns. Storey slab elevations, facade count, base floor elevation and individual machinery shapes still require interpretation from photographs and building descriptions. DTM beneath a building is interpolated bare earth, not a surveyed basement floor. Do not describe a six-storey grid based on the existing 80.75 m display base as a measured 5.14 m floor height. Pinning the main roof at 111.6 m and end structures near 117.6 m is the defensible correction; a photograph-matched facade remains a reconstruction.

Files: `shaw_elevation_audit.json`, `shaw_elevation_samples.npz`, `shaw_elevation_diagnostics.png`; rerun `measure_shaw_elevation.py` for reproducibility.

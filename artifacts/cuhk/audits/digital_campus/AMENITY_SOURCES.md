# CUHK dining and shuttle-stop labels

Checked 27 September 2026. `public/campus/amenities.json` contains **17 dining venues and 25 campus-shuttle stop points**. Every record has a primary source URL, the university map coordinate source, and its original university facility/stop ID. Names are Traditional Chinese with English equivalents.

## Primary sources

- [CUHK dining directory](https://www.cuhk.edu.hk/chinese/campus/accommodation.html): venue names and building/floor addresses, checked against the [English directory](https://www.cuhk.edu.hk/english/campus/accommodation.html).
- [CUHK campus map](https://www.cuhk.edu.hk/chinese/campus/cuhk-campus-map.html) and its linked [coordinate database](https://www.cuhk.edu.hk/chinese/js/campus/cuhk_location_db.js?20200915): published WGS84 point locations. The URL's `20200915` cache parameter is **not** treated as the data date; the dining records include current names, while parts of the shuttle section retain older station names. The university itself notes that map data is not updated in real time.
- [Transport Office shuttle diagram effective 1 September 2026](https://transport.cuhk.edu.hk/wp-content/uploads/documents/Shuttle.pdf): cross-check of current stop names and coverage, without importing routes, timetables, service status or fares.
- [Transport Office notices](https://transport.cuhk.edu.hk/), including [Campus Circuit East downward temporary relocation](https://transport.cuhk.edu.hk/newsdetails/bus-stop-temporary-relocation-campus-circuit-east-downwards/), dated 19 September 2026. The homepage also lists an upward relocation notice dated 28 September. The two affected records explicitly disclose that the saved map marker must not be treated as the current boarding location. No relocation coordinates were inferred from an illustration.

## Dining coverage

All nine colleges have at least one main dining venue: Chung Chi, New Asia, United, Shaw, Morningside, S.H. Ho, CW Chu, Wu Yee Sun and Lee Woo Sing. Benjamin Franklin Centre contributes student, staff and lower-ground venues. Staff/student rooms and the two Lee Woo Sing dining venues retain separate university point locations. United College Si Yuan Amenities Centre is also included.

The layer focuses on canteens and dining halls. It excludes pure cafés, snack bars, shops, private club rooms and off-campus restaurants. The directory marks Postgraduate Hall 3 Canteen closed, so it is excluded. Opening hours and operating status are not copied into the scene.

## Shuttle coverage and limits

The 25 points retain the official map's names and coordinates, including paired points at United College and New Asia College. A direction is retained only where explicitly present in the official map name. Unspecified directions are not inferred from route order or road geometry. The map's two New Asia points retain its common college name; neither is silently renamed “New Asia Circle”.

Older map entries labelled Residence Nos. 3 & 4 (IDs 13/14) and Residence No. 10 (ID 50) are excluded because these names do not match the current shuttle diagram. The current diagram's **Wu Yee Sun College upward/downward stops lack matching named points in this map database** and are not fabricated from the older residence records. The map also supplies only one general point for some locations where the diagram distinguishes directions, such as Shaw College and Area 39. Thus 25 means source-supported map points, not a complete inventory of every current directional boarding stop. Light-bus-only entries and external public-bus stops are outside this layer.

## Coordinates and label height

WGS84 positions are transformed with the existing cached `pyproj` runtime to EPSG:2326, then placed as `[E − 839400, elevation, −(N − 831150)]` in Three.js. Original latitude/longitude remain in every record. No new runtime dependencies were added.

Dining x/z use university map coordinates, not guessed building centres. Their y anchors use the higher of the associated model building's bounding-box roof and four neighbouring heightfield samples, plus 4 m, so markers remain visible. The associated building IDs were checked against their official address and existing scene names; the CW Chu point is about 12 m outside the model footprint, and the Shaw / Wu Yee Sun student points are within about 1 m of footprint edges. These are campus-map markers, not surveyed entrances; this is stated in each dining `locationNote`.

Shuttle y anchors use the maximum of the four enclosing 20 m terrain samples plus 2.5 m. Heights are display anchors rather than measurements of a boarding platform. x/z are not moved onto a guessed road.

## Rebuild and validation

`artifacts/cuhk/build_amenities.py` uses the same bundled Python and existing `.agent-reach/cuhk/python` dependencies as the project's geodata scripts. Its university source cache is `.agent-reach/cuhk/amenities/cuhk_location_db.js`. It parses the source JSON arrays without executing JavaScript. The dated source cache should be reviewed before any future refresh; a rebuild alone does not verify current service changes.

The build includes assertions for expected counts, unique IDs, finite positions, scene bounds, sensible label elevation, valid source URLs and readable Chinese. All 42 records passed. Campus positions are within the existing 2,400 m square scene; “within bounds” is not a claim of entrance or platform survey accuracy. No OSM bus positions were used: the existing OSM caches contain no bus-stop nodes, and the attempted live Overpass requests did not yield usable data.

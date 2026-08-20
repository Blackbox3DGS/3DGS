# Vehicle 3D models

Drop a `car.glb` here. The viewer normalises it to ~4.5 m long and sits the
origin on the ground plane, so any standard glTF car asset works.

## Recommended sources (CC0 / permissive)

- [Sketchfab — CC0 sedan models](https://sketchfab.com/search?features=downloadable&licenses=cc0&q=car&type=models)
- [Quaternius — Ultimate Car pack (CC0)](https://quaternius.com/packs/ultimatecars.html)
- [Poly Pizza — CC0 cars](https://poly.pizza/search/car?cc0=1)

Export as `.glb` (binary glTF). Optimise with `gltf-pipeline -i in.glb -o car.glb -d`
to enable Draco compression — keeps the page-load size under ~2 MB.

If `car.glb` is missing the viewer falls back to a blue rectangular box so
the trajectory animation still demos. Drop the asset in and reload.

## Optional (Phase D 2순위)

- `truck.glb`, `motorcycle.glb`, `bus.glb`

These aren't loaded yet — once the MVS demo works, the viewer will be
extended to look up `class_name` from `trajectories.json` and pick the right
asset per track.

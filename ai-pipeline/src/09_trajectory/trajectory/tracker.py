"""Per-track 3D Kalman filter wrapper around AB3DMOT's `KF` class.

AB3DMOT is licensed for non-commercial research use only (CMU). The KF state
is 10-dim: (x, y, z, theta, l, w, h, vx, vy, vz). We observe only (x, y, z)
from monocular-depth unprojection, so we feed constant dummy values for
theta/l/w/h on every update — their residual is always zero and they have no
effect on the position/velocity estimate.
"""

import os
import sys
from pathlib import Path

import numpy as np

_AB3DMOT_ROOT = os.environ.get(
    "AB3DMOT_ROOT",
    str(Path(__file__).resolve().parents[3] / "third_party" / "AB3DMOT"),
)
if _AB3DMOT_ROOT not in sys.path:
    sys.path.insert(0, _AB3DMOT_ROOT)

from AB3DMOT_libs.kalman_filter import KF  # noqa: E402


_DUMMY_THETA = 0.0
_DUMMY_SIZE = 1.0


class Track3DKalman:
    """Per-track 3D position Kalman filter.

    One instance per track segment. Advance time with `predict()` once per
    frame; fuse an observation with `update(xyz)`. Read `xyz()` and `velocity()`
    after either operation to get the current smoothed estimate.

    `frames_since_update` counts consecutive predict-only ticks since the last
    `update()`; callers use it to detect occlusion gaps and decide when to
    split the track into a new segment (Kalman covariance grows unboundedly
    without observations).
    """

    def __init__(
        self,
        xyz_init,
        track_id: str,
        observation_noise: float = 1.0,
    ):
        bbox3d = np.array(
            [xyz_init[0], xyz_init[1], xyz_init[2],
             _DUMMY_THETA, _DUMMY_SIZE, _DUMMY_SIZE, _DUMMY_SIZE],
            dtype=np.float64,
        )
        self._kf = KF(bbox3d, info=None, ID=track_id)
        self._kf.kf.R[0:3, 0:3] *= observation_noise
        self.frames_since_update = 0

    def predict(self) -> None:
        self._kf.kf.predict()
        self.frames_since_update += 1

    def update(self, xyz) -> None:
        z = np.array(
            [xyz[0], xyz[1], xyz[2],
             _DUMMY_THETA, _DUMMY_SIZE, _DUMMY_SIZE, _DUMMY_SIZE],
            dtype=np.float64,
        )
        self._kf.kf.update(z)
        self.frames_since_update = 0

    def xyz(self) -> tuple[float, float, float]:
        x = self._kf.kf.x.flatten()
        return float(x[0]), float(x[1]), float(x[2])

    def velocity_per_frame(self) -> tuple[float, float, float]:
        x = self._kf.kf.x.flatten()
        return float(x[7]), float(x[8]), float(x[9])

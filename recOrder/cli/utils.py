from pathlib import Path
from typing import Tuple

from iohub.ngff import open_ome_zarr
from iohub.ngff_meta import TransformationMeta
from numpy.typing import DTypeLike


def create_empty_hcs_zarr(
    store_path: Path,
    position_keys: list[Tuple[str]],
    shape: Tuple[int],
    chunks: Tuple[int],
    scale: Tuple[float],
    channel_names: list[str],
    dtype: DTypeLike,
) -> None:
    """Create an empty zarr plate, appending position if they do not exist"""

    # Create plate
    output_plate = open_ome_zarr(
        str(store_path), layout="hcs", mode="a", channel_names=channel_names
    )

    # Create positions
    for position_key in position_keys:
        if "/".join(position_key) not in output_plate.zgroup:
            position = output_plate.create_position(*position_key)

            _ = position.create_zeros(
                name="0",
                shape=shape,
                chunks=chunks,
                dtype=dtype,
                transform=[TransformationMeta(type="scale", scale=scale)],
            )
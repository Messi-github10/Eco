"""Hand a DataFrame to OpenBB.

OpenBB is used here as a result container, not as a data source: the data comes
from AkShare and is wrapped in an ``OBBject`` so the rest of the pipeline can
treat it like any other OpenBB result.
"""

from __future__ import annotations

import pandas as pd
from openbb_core.app.model.obbject import OBBject


def to_obbject(frame: pd.DataFrame, provider: str = "akshare") -> OBBject:
    """Wrap a DataFrame in an OpenBB ``OBBject``.

    ``provider`` records where the data came from. The frame is returned
    unchanged by ``OBBject.to_dataframe()``.
    """
    return OBBject(results=frame, provider=provider)

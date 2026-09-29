"""Export pipeline results to Excel."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl.styles import numbers

# Columns that look numeric but must keep their text form, e.g. a fund code
# whose leading zeros would otherwise be dropped when the file is read back.
TEXT_COLUMNS = ("fund_code",)


def to_excel(frame: pd.DataFrame, path: str | Path, sheet_name: str = "nav") -> Path:
    """Write a DataFrame to an Excel workbook and return the path written.

    Columns listed in ``TEXT_COLUMNS`` are stored as text, so values like the
    fund code ``000001`` survive a round trip through ``pandas.read_excel``.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(target, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name=sheet_name, index=False)
        sheet = writer.sheets[sheet_name]
        for name in TEXT_COLUMNS:
            if name not in frame.columns:
                continue
            column = frame.columns.get_loc(name) + 1
            for cells in sheet.iter_cols(
                min_col=column, max_col=column, min_row=2, max_row=sheet.max_row
            ):
                for cell in cells:
                    cell.number_format = numbers.FORMAT_TEXT
                    if cell.value is not None:
                        cell.value = str(cell.value)
    return target

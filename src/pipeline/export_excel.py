"""Export pipeline results to Excel."""

from __future__ import annotations
from pathlib import Path

import pandas as pd
from openpyxl.styles import numbers

# Columns that look numeric but must keep their text form, e.g. a fund code
# whose leading zeros would otherwise be dropped when the file is read back.
TEXT_COLUMNS = ("fund_code",)


def to_excel(
    frame: pd.DataFrame,
    path: str | Path,
    sheet_name: str = "nav",
    sheets: dict[str, pd.DataFrame] | None = None,
    labels: dict[str, dict[str, str]] | None = None,
) -> Path:
    """Write DataFrames to an Excel workbook and return the path written.

    Pass ``sheets`` to write several named sheets in one file; otherwise a
    single ``frame`` is written under ``sheet_name``. ``labels`` maps a sheet
    name to a column-to-Chinese-label dict; when given, that sheet gets a first
    row of labels above the column names. Columns listed in ``TEXT_COLUMNS``
    are stored as text, so values like the fund code ``000001`` survive a round
    trip through ``pandas.read_excel``.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tables = sheets if sheets is not None else {sheet_name: frame}
    labels = labels or {}

    with pd.ExcelWriter(target, engine="openpyxl") as writer:
        for name, table in tables.items():
            header = labels.get(name)
            startrow = 1 if header else 0
            table.to_excel(writer, sheet_name=name, index=False, startrow=startrow)
            sheet = writer.sheets[name]
            if header:
                _write_label_row(sheet, table, header)
            _write_text_columns(sheet, table, first_data_row=startrow + 2)
    return target


def _write_label_row(sheet, frame: pd.DataFrame, header: dict[str, str]) -> None:
    """Put the Chinese meaning of each column in row 1."""
    for index, column in enumerate(frame.columns, start=1):
        sheet.cell(row=1, column=index, value=header.get(column, ""))


def _write_text_columns(sheet, frame: pd.DataFrame, first_data_row: int) -> None:
    """Force code-like columns to text so leading zeros are not lost."""
    for name in TEXT_COLUMNS:
        if name not in frame.columns:
            continue
        column = frame.columns.get_loc(name) + 1
        for cells in sheet.iter_cols(
            min_col=column, max_col=column, min_row=first_data_row, max_row=sheet.max_row
        ):
            for cell in cells:
                cell.number_format = numbers.FORMAT_TEXT
                if cell.value is not None:
                    cell.value = str(cell.value)

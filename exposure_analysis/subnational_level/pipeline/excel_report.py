"""Reusable "pretty Excel" builder for the wide prioritization tables.

Produces a color-coded, hazard-grouped workbook with a merged two-row header
(hazard display name on top, variable label below), the exposure-class columns
filled with the official CCRI palette (config/class_palette.json), and the
hazard/variable labels from config (hazard_info.json display_name +
column_labels.json).

Both the admin1 (notebook 06) and admin2 (notebook 08) summaries call
``write_wide_excel``; the caller supplies the already-wide DataFrame plus the
column grouping. Nothing here touches Earth Engine.

A "wide" frame for this builder looks like:
    [ front columns... ] [ per-hazard groups... ] [ summary columns... ]
where each per-hazard group is a run of adjacent columns for one hazard.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side


# -- config loading --------------------------------------------------------

def load_report_config(config_dir: str | Path) -> dict:
    """Load palette + labels once; returns a dict the builder consumes."""
    config_dir = Path(config_dir)
    palette = json.loads((config_dir / "class_palette.json").read_text(encoding="utf-8"))
    labels = json.loads((config_dir / "column_labels.json").read_text(encoding="utf-8"))
    hazard_info = pd.read_json(config_dir / "hazard_info.json")
    return {
        "pal_cats": palette["categories"],
        "cat_alias": palette["hazard_info_category_alias"],
        "class_labels": palette["class_labels"],
        "labels": labels,
        # code -> display name / palette category
        "code_display": {r["code"]: r["display_name"] for _, r in hazard_info.iterrows()},
        "code_category": {r["code"]: palette["hazard_info_category_alias"].get(r["category"], r["category"])
                          for _, r in hazard_info.iterrows()},
        "hazard_order": list(hazard_info["code"]),
    }


# -- small helpers ---------------------------------------------------------

def _class_int(v):
    """Coerce a cell value to an int class 1..5, else None (handles '', NaN, floats)."""
    n = pd.to_numeric(v, errors="coerce")
    if pd.isna(n):
        return None
    n = int(n)
    return n if 1 <= n <= 5 else None


def _needs_white_text(hexcode: str) -> bool:
    h = hexcode.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.5


# -- the builder -----------------------------------------------------------

def write_wide_excel(
    df: pd.DataFrame,
    out_path: str,
    *,
    cfg: dict,
    front_cols: list[str],
    group_spans: list[tuple[str, list[str]]],
    summary_cols: list[str] | None = None,
    class_value_suffixes: set[str],
    front_labels: dict[str, str],
    variable_labels: dict[str, str],
    thousands_cols: set[str] | None = None,
    sheet_name: str = "prioritization",
) -> dict:
    """Write ``df`` as a pretty wide Excel.

    Parameters
    ----------
    df : the wide DataFrame (front + grouped hazard columns + summary), row order
         already sorted by the caller.
    group_spans : list of (hazard_code, [column names for that hazard, in order]).
    class_value_suffixes : which value-suffixes are exposure CLASSES to color
         (e.g. {"cexpc", "u18_cexpc"} for admin2, {"cexpc_total", ...} for the
         exposure view). A group column ``{code}__{suffix}`` or ``{code}_{suffix}``
         is colored if its suffix is in this set.
    front_labels / variable_labels : header text lookups.
    thousands_cols : exact column names to format as ``#,##0``.

    Returns a small summary dict.
    """
    summary_cols = summary_cols or []
    thousands_cols = thousands_cols or set()
    pal_cats, class_labels = cfg["pal_cats"], cfg["class_labels"]
    code_display, code_category = cfg["code_display"], cfg["code_category"]

    final_cols = list(front_cols) + [c for _, cols in group_spans for c in cols] + list(summary_cols)

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    H1, H2, DATA0 = 1, 2, 3

    hdr_fill = PatternFill("solid", fgColor="FF305496")
    front_fill = PatternFill("solid", fgColor="FF548235")
    summ_fill = PatternFill("solid", fgColor="FF7F7F7F")
    hdr_font = Font(color="FFFFFF", bold=True)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin = Side(style="thin", color="DDDDDD")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    col = 1
    # front columns: label spans both header rows
    for name in front_cols:
        ws.merge_cells(start_row=H1, start_column=col, end_row=H2, end_column=col)
        c = ws.cell(H1, col, front_labels.get(name, name))
        c.fill = front_fill if name in front_labels and name not in ("adm1_ucode", "adm1_name", "adm2_ucode", "adm2_name") else hdr_fill
        c.font = hdr_font
        c.alignment = center
        col += 1
    # hazard groups: merged display name on row1, variable label on row2
    for code, cols in group_spans:
        start = col
        for cn in cols:
            # suffix after the last "__" or the code prefix
            suffix = cn.split("__", 1)[1] if "__" in cn else cn[len(code) + 1:]
            c2 = ws.cell(H2, col, variable_labels.get(suffix, suffix))
            c2.fill = hdr_fill; c2.font = hdr_font; c2.alignment = center; c2.border = border
            col += 1
        ws.merge_cells(start_row=H1, start_column=start, end_row=H1, end_column=col - 1)
        c1 = ws.cell(H1, start, code_display.get(code, code))
        c1.fill = hdr_fill; c1.font = hdr_font; c1.alignment = center; c1.border = border
    # summary columns
    for name in summary_cols:
        ws.merge_cells(start_row=H1, start_column=col, end_row=H2, end_column=col)
        c = ws.cell(H1, col, variable_labels.get(name, name))
        c.fill = summ_fill; c.font = hdr_font; c.alignment = center
        col += 1

    # data
    for i, (_, row) in enumerate(df[final_cols].iterrows()):
        for j, name in enumerate(final_cols, start=1):
            ws.cell(DATA0 + i, j, row[name] if pd.notna(row[name]) else None)

    name_to_col = {name: j for j, name in enumerate(final_cols, start=1)}

    # color the class columns of each hazard group
    colored = 0
    for code, cols in group_spans:
        cat = code_category.get(code)
        if cat is None:
            continue
        for cn in cols:
            suffix = cn.split("__", 1)[1] if "__" in cn else cn[len(code) + 1:]
            if suffix not in class_value_suffixes:
                continue
            ci = name_to_col[cn]
            for i in range(len(df)):
                cell = ws.cell(DATA0 + i, ci)
                n = _class_int(cell.value)
                if n is None:
                    continue
                hexc = pal_cats.get(cat, {}).get(class_labels[n - 1])
                if not hexc:
                    continue
                argb = "FF" + hexc.lstrip("#").upper()
                cell.fill = PatternFill("solid", fgColor=argb)
                cell.font = Font(color="FFFFFF", bold=True) if _needs_white_text(hexc) else Font(bold=True)
                cell.alignment = Alignment(horizontal="center")
                cell.border = border
                colored += 1

    # thousands formatting
    for name in thousands_cols:
        if name in name_to_col:
            j = name_to_col[name]
            for i in range(len(df)):
                ws.cell(DATA0 + i, j).number_format = "#,##0"

    # freeze below the header, right of the front id columns (first 2 front cols)
    ws.freeze_panes = f"{_col_letter(len(front_cols) + 1)}{DATA0}"
    wb.save(out_path)
    return {"path": out_path, "rows": len(df), "hazard_groups": len(group_spans), "class_cells": colored}


def _col_letter(idx: int) -> str:
    from openpyxl.utils import get_column_letter
    return get_column_letter(idx)

import re
from pathlib import Path
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd
from django.conf import settings


# ---------- Helpers ----------

def _datasets_dir() -> Path:
    # Folder next to manage.py
    return Path(settings.BASE_DIR) / "datasets"


YEAR_RX = re.compile(r"^([Yy]?)(19|20)\d{2}$")  # "1990" or "Y1990" etc.
SA_ALIASES = {
    "south africa",
    "south africa, rep.",
    "south africa (republic of)",
    "south africa republic",
    "republic of south africa",
}


def _detect_year_cols(df: pd.DataFrame) -> List[str]:
    cols = []
    for c in map(str, df.columns):
        if YEAR_RX.match(c.strip()):
            cols.append(c)
    return cols


def _detect_country_col(df: pd.DataFrame) -> Optional[str]:
    candidates = [c for c in df.columns if re.search(r"country|ref_area|location|economy", str(c), re.I)]
    if candidates:
        # prefer shorter, human-readable ones
        candidates.sort(key=lambda x: len(str(x)))
        return str(candidates[0])
    return None


def _ensure_shared_country(gdf: pd.DataFrame, idf: pd.DataFrame) -> str:
    """Return a country column name that exists in BOTH; create one if needed."""
    cg, ci = _detect_country_col(gdf), _detect_country_col(idf)

    if cg and ci:
        if cg == ci:
            return str(cg)
        # different names → create unified "Country"
        gdf["Country"] = gdf[str(cg)]
        idf["Country"] = idf[str(ci)]
        return "Country"

    if cg and not ci:
        idf["Country"] = idf[str(cg)] if str(cg) in idf.columns else "South Africa"
        gdf["Country"] = gdf[str(cg)]
        return "Country"

    if ci and not cg:
        gdf["Country"] = gdf[str(ci)] if str(ci) in gdf.columns else "South Africa"
        idf["Country"] = idf[str(ci)]
        return "Country"

    # Neither has a country column → assume single-country files; create one
    gdf["Country"] = "South Africa"
    idf["Country"] = "South Africa"
    return "Country"


def _melt(df: pd.DataFrame, country_col: str, value_name: str) -> pd.DataFrame:
    year_cols = _detect_year_cols(df)
    if not year_cols:
        # last-ditch: treat anything that looks numeric-ish as a year
        year_cols = [c for c in df.columns if str(c).strip().isdigit()]

    if not year_cols:
        # give up gracefully with empty frame; caller will handle
        return pd.DataFrame(columns=[country_col, "Year", value_name])

    long_df = df.melt(id_vars=[country_col], value_vars=year_cols, var_name="Year", value_name=value_name)
    # normalize "Y1990" -> "1990"
    long_df["Year"] = long_df["Year"].astype(str).str.extract(r"(\d{4})").astype("Int64")
    long_df = long_df.dropna(subset=["Year"]).astype({"Year": int})
    long_df[value_name] = pd.to_numeric(long_df[value_name], errors="coerce")
    return long_df


def _pick_sa_name(unique_names: List[str]) -> Optional[str]:
    # Try to find a SA variant in provided names
    for name in unique_names:
        if str(name).strip().lower() in SA_ALIASES:
            return str(name)
    # try contains
    for name in unique_names:
        if "south africa" in str(name).lower():
            return str(name)
    return None


def _dataset_quick_facts(df_original: pd.DataFrame, df_long: pd.DataFrame, country_col: str, name: str) -> Dict[str, Any]:
    cols: List[str] = list(map(str, df_original.columns))
    y_min = int(df_long["Year"].min()) if not df_long.empty else None
    y_max = int(df_long["Year"].max()) if not df_long.empty else None
    values = df_long.iloc[:, -1].to_numpy(float) if not df_long.empty else np.array([])
    non_null = int(np.isfinite(values).sum()) if values.size else 0
    nulls = int(np.isnan(values).sum()) if values.size else 0
    return {
        "name": name,
        "country_col": country_col,
        "row_count": int(df_original.shape[0]),
        "columns_preview": cols[:8],
        "year_min": y_min,
        "year_max": y_max,
        "non_null_points": non_null,
        "null_points": nulls,
    }


def _rolling(arr: np.ndarray, window: int = 5) -> np.ndarray:
    if len(arr) < window:
        return np.array([])
    return np.convolve(arr, np.ones(window), "valid") / window


def _rolling_std(arr: np.ndarray, window: int = 5) -> np.ndarray:
    if len(arr) < window:
        return np.array([])
    return np.array([float(np.nanstd(arr[i - window + 1:i + 1])) for i in range(window - 1, len(arr))])


# ---------- Main entry ----------

def load_and_compute(country: str = "South Africa") -> Dict[str, Any]:
    ddir = _datasets_dir()
    gdp_path = ddir / "GDP.csv"
    inf_path = ddir / "Inflation1.csv"

    if not gdp_path.exists() or not inf_path.exists():
        return {"ok": False, "error": f"Missing CSV files in {ddir} (need GDP.csv and Inflation1.csv)."}

    gdf = pd.read_csv(gdp_path)
    idf = pd.read_csv(inf_path)

    # unify a country column across both frames
    country_col = _ensure_shared_country(gdf, idf)

    # melt into long form
    g_long = _melt(gdf, country_col, "GDP")
    i_long = _melt(idf, country_col, "Inflation")

    # dataset facts for the modal
    g_facts = _dataset_quick_facts(gdf, g_long, country_col, "GDP.csv")
    i_facts = _dataset_quick_facts(idf, i_long, country_col, "Inflation1.csv")

    # choose the actual country row
    chosen_country = country
    if country_col not in gdf.columns or country_col not in idf.columns:
        chosen_country = "South Africa"  # synthetic
    else:
        # if SA not present, pick the first country and report it
        available = sorted(set(map(str, gdf[country_col].dropna().unique())))
        sa_name = _pick_sa_name(available)
        if sa_name:
            chosen_country = sa_name
        elif country not in available and available:
            chosen_country = available[0]

    g_long = g_long[g_long[country_col] == chosen_country]
    i_long = i_long[i_long[country_col] == chosen_country]

    # merge; DROP missing (your preference)
    merged = (
        i_long.merge(g_long, on=[country_col, "Year"], how="inner")
              .rename(columns={country_col: "Country"})
              .dropna(subset=["Inflation", "GDP"])
              .sort_values("Year")
              .reset_index(drop=True)
    )

    diagnostics = {
        "expected_country": country,
        "used_country": chosen_country,
        "country_col": country_col,
        "gdp_year_cols": _detect_year_cols(gdf),
        "infl_year_cols": _detect_year_cols(idf),
        "gdp_rows": int(gdf.shape[0]),
        "infl_rows": int(idf.shape[0]),
    }

    if merged.empty:
        return {"ok": False, "error": "No overlapping data after merge. Check year columns or country names.",
                "diagnostics": diagnostics}

    years = merged["Year"].to_numpy()
    gdp = merged["GDP"].to_numpy(float)
    infl = merged["Inflation"].to_numpy(float)

    # KPIs
    def _safe(stat, arr):
        try:
            return float(np.round(stat(arr), 2))
        except Exception:
            return None

    kpi = {
        "records": int(len(merged)),
        "unique_years": int(merged["Year"].nunique()),
        "inflation_mean": _safe(np.nanmean, infl),
        "inflation_std":  _safe(np.nanstd, infl),
        "gdp_mean":       _safe(np.nanmean, gdp),
        "gdp_std":        _safe(np.nanstd, gdp),
        "corr_gdp_inflation": float(np.round(np.corrcoef(gdp, infl)[0, 1], 3)) if len(merged) >= 2 else None,
        "inflation_min":  _safe(np.nanmin, infl),
        "inflation_max":  _safe(np.nanmax, infl),
        "gdp_min":        _safe(np.nanmin, gdp),
        "gdp_max":        _safe(np.nanmax, gdp),
    }

    # YoY
    if len(years) > 1:
        yoy_years = years[1:]
        gdp_yoy = np.diff(gdp)
        infl_yoy = np.diff(infl)
    else:
        yoy_years = np.array([], dtype=int)
        gdp_yoy = np.array([], dtype=float)
        infl_yoy = np.array([], dtype=float)

    # Rolling (5)
    win = 5
    gdp_ma = _rolling(gdp, win)
    infl_ma = _rolling(infl, win)
    infl_std = _rolling_std(infl, win)
    roll_years = years[win - 1:] if len(years) >= win else np.array([], dtype=int)

    # Decades
    def _decade(y: int) -> str: return f"{(y // 10) * 10}s"
    merged["Decade"] = merged["Year"].apply(_decade)
    dec = merged.groupby("Decade").agg(gdp_mean=("GDP", "mean"),
                                       infl_mean=("Inflation", "mean")).reset_index()
    dec = dec.sort_values("Decade")
    dec_labels = dec["Decade"].tolist()
    dec_gdp = [float(np.round(x, 2)) for x in dec["gdp_mean"].tolist()]
    dec_infl = [float(np.round(x, 2)) for x in dec["infl_mean"].tolist()]

    # Regression line (GDP ~ Inflation)
    if len(merged) >= 2:
        x, y = infl, gdp
        xm, ym = np.mean(x), np.mean(y)
        denom = np.sum((x - xm) ** 2)
        slope = float(np.sum((x - xm) * (y - ym)) / denom) if denom else 0.0
        intercept = float(ym - slope * xm)
    else:
        slope, intercept = 0.0, 0.0

    # Donut counts
    pos = int(np.sum(gdp_yoy > 0))
    neg = int(np.sum(gdp_yoy < 0))
    zero = int(np.sum(gdp_yoy == 0))

    # Cumulative GDP growth from first year
    cum_gdp = (gdp / gdp[0] - 1.0).tolist() if len(gdp) else []

    # Inflation histogram
    if len(infl):
        hist_counts, hist_edges = np.histogram(infl, bins=12)
        hist_centers = ((hist_edges[:-1] + hist_edges[1:]) / 2.0).tolist()
        hist_counts = hist_counts.astype(int).tolist()
    else:
        hist_centers, hist_counts = [], []

    return {
        "ok": True,
        "country": str(chosen_country),
        "diagnostics": diagnostics,
        "meta": {
            "datasets": {
                "gdp": _dataset_quick_facts(gdf, g_long, country_col, "GDP.csv"),
                "inflation": _dataset_quick_facts(idf, i_long, country_col, "Inflation1.csv"),
            }
        },
        "series": {
            "years": years.tolist(),
            "gdp": [float(np.round(x, 6)) for x in gdp],
            "inflation": [float(np.round(x, 6)) for x in infl],
        },
        "yoy": {
            "years": yoy_years.tolist(),
            "gdp": [float(np.round(x, 6)) for x in gdp_yoy],
            "inflation": [float(np.round(x, 6)) for x in infl_yoy],
            "summary": {"positive": pos, "negative": neg, "zero": zero},
        },
        "rolling": {
            "years": roll_years.tolist(),
            "gdp_ma": [float(np.round(x, 6)) for x in gdp_ma],
            "infl_ma": [float(np.round(x, 6)) for x in infl_ma],
            "infl_std": [float(np.round(x, 6)) for x in infl_std],
            "window": win,
        },
        "decades": {
            "labels": dec_labels,
            "gdp_mean": dec_gdp,
            "infl_mean": dec_infl,
        },
        "regression": {
            "slope": float(np.round(slope, 6)),
            "intercept": float(np.round(intercept, 6)),
            "x_min": float(np.min(infl)) if len(infl) else 0.0,
            "x_max": float(np.max(infl)) if len(infl) else 1.0,
        },
        "extra": {
            "cum_gdp": [float(np.round(x, 6)) for x in cum_gdp],
            "infl_hist_centers": hist_centers,
            "infl_hist_counts": hist_counts,
        },
        "kpi": kpi,
    }

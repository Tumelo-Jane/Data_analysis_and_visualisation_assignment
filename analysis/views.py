from __future__ import annotations
import csv
import math
import statistics
import os
from pathlib import Path
from typing import Dict, List, Optional
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import render

# ========= PATHS (robust resolution to your python_analytics/datasets) =========
# views.py path: ...\data_analysis_project\data_analysis\analysis\views.py
HERE = Path(__file__).resolve()
# Go up to the assignment root: ...\Data_analysis_and_visualisation_assignment
ASSIGNMENT_ROOT = HERE.parents[3]

# Allow explicit override via env var if you ever want it:
ENV_DATASETS = os.environ.get("DA_DATASETS", "")

CANDIDATES = [
    # Your real location (relative to assignment root)
    ASSIGNMENT_ROOT / "python_analytics" / "datasets",
    # Common alternates:
    HERE.parents[2] / "datasets",                          # ...\data_analysis_project\data_analysis\datasets
    HERE.parents[3] / "datasets",                          # ...\data_analysis_project\datasets
    Path(ENV_DATASETS) if ENV_DATASETS else None,
    # Absolute fallback you told me (kept last; OK to remove later)
    Path(r"C:\Users\Admin.DESKTOP-UD6VIR4\Desktop\Data Anlysis and Visualization Assignment\Data_analysis_and_visualisation_assignment\python_analytics\datasets"),
]

DATA_DIR = next((p for p in CANDIDATES if p and p.exists()), None)
if not DATA_DIR:
    # Fail loudly so you see the exact places it looked
    raise FileNotFoundError(
        "Could not locate datasets folder. Tried:\n" +
        "\n".join(str(p) for p in CANDIDATES if p)
    )

COUNTRY = "South Africa"
GDP_FILE = DATA_DIR / "GDP.csv"
INFL_FILE = DATA_DIR / "Inflation1.csv"

# ==================== helpers ====================
def _is_year(k: str) -> bool:
    return k.isdigit() and 1900 <= int(k) <= 2100

def _to_float(x: str) -> Optional[float]:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except Exception:
        return None

def load_country_series(path: Path, country_name: str):
    """
    Reads a wide CSV where columns are years and a row is the country.
    Returns (years, values, meta) with years sorted and values aligned.
    """
    if not path.exists():
        return [], [], {
            "name": path.name, "row_count": 0, "year_min": None, "year_max": None,
            "non_null_points": 0, "null_points": 0, "columns_preview": []
        }

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cname = row.get("REF_AREA_NAME") or row.get("Country")
            if cname and cname.strip().lower() == country_name.lower():
                year_keys = [int(k) for k in row.keys() if _is_year(k)]
                year_keys.sort()
                vals = [_to_float(row[str(y)]) for y in year_keys]
                non_null = sum(1 for v in vals if v is not None)
                meta = {
                    "name": path.name,
                    "row_count": non_null,
                    "year_min": year_keys[0] if year_keys else None,
                    "year_max": year_keys[-1] if year_keys else None,
                    "non_null_points": non_null,
                    "null_points": len(vals) - non_null,
                    "columns_preview": [c for c in (reader.fieldnames or []) if not _is_year(c)][:4]
                                       + [str(y) for y in year_keys[:6]],
                }
                return year_keys, vals, meta

    return [], [], {
        "name": path.name, "row_count": 0, "year_min": None, "year_max": None,
        "non_null_points": 0, "null_points": 0, "columns_preview": []
    }

def align_overlap(yrs_a, vals_a, yrs_b, vals_b):
    a = {y: v for y, v in zip(yrs_a, vals_a) if v is not None}
    b = {y: v for y, v in zip(yrs_b, vals_b) if v is not None}
    common = sorted(set(a) & set(b))
    return common, [a[y] for y in common], [b[y] for y in common]

def mean_safe(x: List[float]) -> float:
    return float(statistics.fmean(x)) if x else 0.0

def corr(x: List[float], y: List[float]) -> float:
    if len(x) < 2 or len(y) < 2 or len(x) != len(y):
        return float("nan")
    mx, my = mean_safe(x), mean_safe(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    denx = math.sqrt(sum((a - mx) ** 2 for a in x))
    deny = math.sqrt(sum((b - my) ** 2 for b in y))
    return num / (denx * deny) if denx and deny else float("nan")

def linreg(x: List[float], y: List[float]):
    if len(x) < 2:
        return 0.0, 0.0
    mx, my = mean_safe(x), mean_safe(y)
    denom = sum((a - mx) ** 2 for a in x)
    if denom == 0:
        return 0.0, my
    m = sum((a - mx) * (b - my) for a, b in zip(x, y)) / denom
    b = my - m * mx
    return m, b

def decade_label(y: int) -> str:
    return f"{(y // 10) * 10}s"

def rolling_mean(arr: List[float], w: int) -> List[float]:
    if w <= 1 or len(arr) < w:
        return []
    out, s = [], sum(arr[:w])
    out.append(s / w)
    for i in range(w, len(arr)):
        s += arr[i] - arr[i - w]
        out.append(s / w)
    return out

def rolling_std(arr: List[float], w: int) -> List[float]:
    if w <= 1 or len(arr) < w:
        return []
    out = []
    for i in range(w - 1, len(arr)):
        seg = arr[i - w + 1 : i + 1]
        out.append(statistics.pstdev(seg))
    return out

def hist_counts(arr: List[float], bins: int = 10):
    if not arr:
        return [], []
    lo, hi = min(arr), max(arr)
    if hi == lo:
        return [lo], [len(arr)]
    step = (hi - lo) / bins
    edges = [lo + i * step for i in range(bins + 1)]
    counts = [0] * bins
    for v in arr:
        if v == hi:
            counts[-1] += 1
        else:
            idx = int((v - lo) / step)
            counts[idx] += 1
    centers = [(edges[i] + edges[i + 1]) / 2 for i in range(bins)]
    return centers, counts

# ==================== views ====================
def dashboard(request: HttpRequest) -> HttpResponse:
    return render(request, "analysis/dashboard.html", {})

def database(request: HttpRequest) -> HttpResponse:
    return render(request, "analysis/database.html", {})

def metrics_api(request: HttpRequest) -> JsonResponse:
    yrs_gdp, val_gdp, meta_gdp = load_country_series(GDP_FILE, COUNTRY)
    yrs_infl, val_infl, meta_infl = load_country_series(INFL_FILE, COUNTRY)

    solo_g_years = [y for y, v in zip(yrs_gdp, val_gdp) if v is not None]
    solo_g_vals  = [v for v in val_gdp if v is not None]
    solo_i_years = [y for y, v in zip(yrs_infl, val_infl) if v is not None]
    solo_i_vals  = [v for v in val_infl if v is not None]

    years, gdp, infl = align_overlap(yrs_gdp, val_gdp, yrs_infl, val_infl)

    infl_mean = mean_safe(infl)
    infl_std  = float(statistics.pstdev(infl)) if len(infl) > 1 else 0.0
    infl_min  = min(infl) if infl else 0.0
    infl_max  = max(infl) if infl else 0.0
    gdp_max   = max(gdp) if gdp else 0.0

    c = corr(infl, gdp)
    m, b = linreg(infl, gdp)
    x_min = min(infl) if infl else 0.0
    x_max = max(infl) if infl else 0.0

    yoy_gdp = [gdp[i] - gdp[i - 1] for i in range(1, len(gdp))]
    yoy_years = years[1:] if years else []
    pos = sum(1 for v in yoy_gdp if v > 0)
    neg = sum(1 for v in yoy_gdp if v < 0)
    zero = sum(1 for v in yoy_gdp if v == 0)

    by_dec: Dict[str, Dict[str, List[float]]] = {}
    for y, g, i in zip(years, gdp, infl):
        d = decade_label(y)
        by_dec.setdefault(d, {"g": [], "i": []})
        by_dec[d]["g"].append(g)
        by_dec[d]["i"].append(i)
    dec_labels = sorted(by_dec.keys(), key=lambda s: int(s[:-1]))
    dec_g_mean = [mean_safe(by_dec[d]["g"]) for d in dec_labels]
    dec_i_mean = [mean_safe(by_dec[d]["i"]) for d in dec_labels]

    window = 5
    roll_years = years[window - 1 :] if len(years) >= window else []
    roll_gdp_ma = rolling_mean(gdp, window)
    roll_infl_ma = rolling_mean(infl, window)
    roll_infl_std = rolling_std(infl, window)

    hist_centers, hist_counts_ = hist_counts(solo_i_vals, bins=10)

    # simple cumulative “from first year” path
    cum = []
    if gdp:
        base = gdp[0]
        acc = 0.0
        for v in gdp:
            acc += (v - base)
            cum.append(acc)

    payload = {
        "ok": True,
        "meta": {
            "datasets": {"gdp": meta_gdp, "inflation": meta_infl},
            "coverage": {
                "gdp": {"min": solo_g_years[0] if solo_g_years else None,
                        "max": solo_g_years[-1] if solo_g_years else None},
                "inflation": {"min": solo_i_years[0] if solo_i_years else None,
                              "max": solo_i_years[-1] if solo_i_years else None},
                "both": {"min": years[0] if years else None,
                         "max": years[-1] if years else None},
            },
        },
        "kpi": {
            "records": len(years),
            "unique_years": len(set(years)),
            "inflation_mean": infl_mean,
            "inflation_std": infl_std,
            "inflation_min": infl_min,
            "inflation_max": infl_max,
            "gdp_max": gdp_max,
            "corr_gdp_inflation": c,
        },
        "series": {"years": years, "gdp": gdp, "inflation": infl},
        "solo": {
            "gdp": {"years": solo_g_years, "values": solo_g_vals},
            "infl": {"years": solo_i_years, "values": solo_i_vals},
        },
        "yoy": {
            "years": yoy_years,
            "gdp": yoy_gdp,
            "summary": {"positive": pos, "negative": neg, "zero": zero},
            "inflation": [solo_i_vals[i] - solo_i_vals[i - 1] for i in range(1, len(solo_i_vals))]
                          if len(solo_i_vals) > 1 else [],
        },
        "decades": {"labels": dec_labels, "gdp_mean": dec_g_mean, "infl_mean": dec_i_mean},
        "rolling": {
            "window": window,
            "years": roll_years,
            "gdp_ma": roll_gdp_ma,
            "infl_ma": roll_infl_ma,
            "infl_std": roll_infl_std,
        },
        "extra": {"infl_hist_centers": hist_centers, "infl_hist_counts": hist_counts_, "cum_gdp": cum},
        "regression": {"slope": m, "intercept": b, "x_min": x_min, "x_max": x_max},
    }
    return JsonResponse(payload)

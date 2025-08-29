# analysis/views.py
from __future__ import annotations

import csv
import math
import os
import statistics
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

# ---------------- Paths (robust) ----------------
HERE = Path(__file__).resolve()

ASSIGNMENT_ROOT_CANDIDATES = [HERE.parents[4], HERE.parents[3]]
ENV_DATASETS = os.environ.get("DA_DATASETS", "")

CANDIDATES: List[Optional[Path]] = [
    *(p / "python_analytics" / "datasets" for p in ASSIGNMENT_ROOT_CANDIDATES if p),
    HERE.parents[2] / "datasets",  # …/data_analysis/analysis/../datasets
    HERE.parents[3] / "datasets",  # …/data_analysis/../datasets
    Path(ENV_DATASETS) if ENV_DATASETS else None,
]

DATA_DIR = next((p for p in CANDIDATES if p and p.exists()), None)
if not DATA_DIR:
    raise FileNotFoundError(
        "Datasets folder not found. Tried:\n" + "\n".join(str(p) for p in CANDIDATES if p)
    )

COUNTRY = "South Africa"
GDP_FILE = DATA_DIR / "GDP.csv"
INFL_FILE = DATA_DIR / "Inflation1.csv"

# ---------------- Helpers ----------------
def _is_year(k: str) -> bool:
    return k.isdigit() and 1900 <= int(k) <= 2100

def _to_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        s = str(x).strip()
        if s == "" or s.lower() == "nan":
            return None
        s = s.replace(" ", "").replace(",", "")  # support "12,345.6"
        return float(s)
    except Exception:
        return None

def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()

def _empty_meta(name: str) -> Dict:
    return {
        "name": name,
        "row_count": 0,
        "year_min": None,
        "year_max": None,
        "non_null_points": 0,
        "null_points": 0,
        "columns_preview": [],
    }

# ---- auto-detect WIDE vs LONG and extract series ----
def load_country_series(path: Path, country_name: str) -> Tuple[List[int], List[Optional[float]], Dict]:
    """
    Returns (years:int[], values:float|None[], meta:dict)
    Supports:
      - WIDE: one row per country; year columns like '1990','1991',...
      - LONG: columns like Year/TIME_PERIOD + Value/OBS_VALUE (+ optional country)
    """
    if not path.exists():
        return [], [], _empty_meta(path.name)

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return [], [], _empty_meta(path.name)
        fields = [c.strip() for c in reader.fieldnames]
        rows = list(reader)

    year_cols = [c for c in fields if _is_year(c)]
    country_cols = ["REF_AREA_NAME", "Country", "Country Name", "Country_Name", "REF_AREA"]
    time_cols = ["TIME_PERIOD", "Year", "YEAR", "time_period", "year"]
    value_cols = ["OBS_VALUE", "Value", "VALUE", "obs_value", "value"]

    # ---------- WIDE ----------
    if len(year_cols) >= 2:
        ccol = next((c for c in country_cols if c in fields), None)
        hit_row = None
        if ccol:
            for row in rows:
                if _norm(row.get(ccol)) == _norm(country_name):
                    hit_row = row
                    break
        else:
            hit_row = rows[0] if rows else None

        if not hit_row:
            return [], [], _empty_meta(path.name)

        years = sorted(int(y) for y in year_cols)
        vals = [_to_float(hit_row.get(str(y))) for y in years]
        non_null = sum(1 for v in vals if v is not None)
        meta = {
            "name": path.name,
            "row_count": non_null,
            "year_min": years[0] if years else None,
            "year_max": years[-1] if years else None,
            "non_null_points": non_null,
            "null_points": len(vals) - non_null,
            "columns_preview": ([ccol] if ccol else []) + [str(y) for y in years[:6]],
        }
        return years, vals, meta

    # ---------- LONG ----------
    tcol = next((c for c in time_cols if c in fields), None)
    vcol = next((c for c in value_cols if c in fields), None)
    ccol = next((c for c in country_cols if c in fields), None)

    if not (tcol and vcol):
        return [], [], _empty_meta(path.name)

    if ccol:
        rows = [r for r in rows if _norm(r.get(ccol)) == _norm(country_name)]

    by_year: Dict[int, Optional[float]] = {}
    for r in rows:
        y_raw = r.get(tcol)
        if y_raw is None:
            continue
        try:
            y = int(str(y_raw).strip()[:4])  # handle "1990-01-01"
        except Exception:
            continue
        v = _to_float(r.get(vcol))
        if v is not None:
            by_year[y] = v

    years = sorted(by_year.keys())
    vals = [by_year[y] for y in years]
    non_null = sum(1 for v in vals if v is not None)
    meta = {
        "name": path.name,
        "row_count": non_null,
        "year_min": years[0] if years else None,
        "year_max": years[-1] if years else None,
        "non_null_points": non_null,
        "null_points": len(vals) - non_null,
        "columns_preview": [c for c in ([ccol] if ccol else [])] + [tcol, vcol],
    }
    return years, vals, meta

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
# --- Add under the other helpers ---
def preview_rows(path: Path, country_name: str, limit: int = 10):
    """Return first N (year, value) rows (non-null) for a given country."""
    years, vals, _ = load_country_series(path, country_name)
    rows = [{"year": y, "value": v} for y, v in zip(years, vals) if v is not None]
    return rows[:max(0, int(limit))]

# --- Add near the other views ---
def preview_api(request: HttpRequest) -> JsonResponse:
    kind = (request.GET.get("kind") or "").lower()
    limit = int(request.GET.get("limit") or 10)
    if kind not in {"gdp", "inflation"}:
        return JsonResponse({"ok": False, "error": "kind must be 'gdp' or 'inflation'"}, status=400)

    path = GDP_FILE if kind == "gdp" else INFL_FILE
    rows = preview_rows(path, COUNTRY, limit=limit)
    return JsonResponse({"ok": True, "rows": rows})


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
            counts[int((v - lo) / step)] += 1
    centers = [(edges[i] + edges[i + 1]) / 2 for i in range(bins)]
    return centers, counts

# ---------------- Templates ----------------
def dashboard(request: HttpRequest) -> HttpResponse:
    return render(request, "analysis/dashboard.html", {})

def database(request: HttpRequest) -> HttpResponse:
    return render(request, "analysis/database.html", {})

# ---------------- APIs ----------------
def metrics_api(request: HttpRequest) -> JsonResponse:
    yrs_gdp, val_gdp, meta_gdp = load_country_series(GDP_FILE, COUNTRY)
    yrs_infl, val_infl, meta_infl = load_country_series(INFL_FILE, COUNTRY)

    solo_g_years = [y for y, v in zip(yrs_gdp, val_gdp) if v is not None]
    solo_g_vals = [v for v in val_gdp if v is not None]
    solo_i_years = [y for y, v in zip(yrs_infl, val_infl) if v is not None]
    solo_i_vals = [v for v in val_infl if v is not None]

    years, gdp, infl = align_overlap(yrs_gdp, val_gdp, yrs_infl, val_infl)

    infl_mean = mean_safe(infl)
    infl_std = float(statistics.pstdev(infl)) if len(infl) > 1 else 0.0
    infl_min = min(infl) if infl else 0.0
    infl_max = max(infl) if infl else 0.0

    gdp_mean = mean_safe(gdp)
    gdp_std = float(statistics.pstdev(gdp)) if len(gdp) > 1 else 0.0
    gdp_min = min(gdp) if gdp else 0.0
    gdp_max = max(gdp) if gdp else 0.0

    r = corr(gdp, infl)

    yoy_years = years[1:] if years else []
    yoy_gdp = [gdp[i] - gdp[i - 1] for i in range(1, len(gdp))]
    yoy_infl = [infl[i] - infl[i - 1] for i in range(1, len(infl))]
    pos = sum(1 for v in yoy_gdp if v > 0)
    neg = sum(1 for v in yoy_gdp if v < 0)
    zero = sum(1 for v in yoy_gdp if v == 0)

    pre_mask = [y <= 1993 for y in years]
    post_mask = [y >= 1994 for y in years]
    def pick(arr, mask): return [v for v, m in zip(arr, mask) if m]
    g_pre, g_post = pick(gdp, pre_mask), pick(gdp, post_mask)
    i_pre, i_post = pick(infl, pre_mask), pick(infl, post_mask)
    def std_safe(a): return float(statistics.pstdev(a)) if len(a) > 1 else 0.0

    apartheid = {
        "means": {
            "gdp_pre": mean_safe(g_pre),
            "gdp_post": mean_safe(g_post),
            "infl_pre": mean_safe(i_pre),
            "infl_post": mean_safe(i_post),
        },
        "std": {
            "gdp_pre": std_safe(g_pre),
            "gdp_post": std_safe(g_post),
            "infl_pre": std_safe(i_pre),
            "infl_post": std_safe(i_post),
        },
        "counts": {"pre_years": len(g_pre), "post_years": len(g_post)},
    }

    best_gdp_idx = int(gdp.index(max(gdp))) if gdp else 0
    worst_gdp_idx = int(gdp.index(min(gdp))) if gdp else 0
    best_inf_idx = int(infl.index(min(infl))) if infl else 0
    worst_inf_idx = int(infl.index(max(infl))) if infl else 0
    extremes = {
        "best_gdp": {"year": years[best_gdp_idx] if years else None, "value": gdp[best_gdp_idx] if gdp else 0.0},
        "worst_gdp": {"year": years[worst_gdp_idx] if years else None, "value": gdp[worst_gdp_idx] if gdp else 0.0},
        "best_infl": {"year": years[best_inf_idx] if years else None, "value": infl[best_inf_idx] if infl else 0.0},
        "worst_infl": {"year": years[worst_inf_idx] if years else None, "value": infl[worst_inf_idx] if infl else 0.0},
    }

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

    cum: List[float] = []
    acc = 0.0
    for v in gdp:
        acc += v
        cum.append(acc)

    m, b = linreg(infl, gdp)
    x_min = min(infl) if infl else 0.0
    x_max = max(infl) if infl else 0.0

    payload = {
        "ok": True,
        "meta": {
            "datasets": {"gdp": meta_gdp, "inflation": meta_infl},
            "coverage": {
                "gdp": {"min": solo_g_years[0] if solo_g_years else None, "max": solo_g_years[-1] if solo_g_years else None},
                "inflation": {"min": solo_i_years[0] if solo_i_years else None, "max": solo_i_years[-1] if solo_i_years else None},
                "both": {"min": years[0] if years else None, "max": years[-1] if years else None},
            },
        },
        "kpi": {
            "records": len(years),
            "unique_years": len(set(years)),
            "inflation_mean": infl_mean,
            "inflation_std": infl_std,
            "inflation_min": infl_min,
            "inflation_max": infl_max,
            "gdp_mean": gdp_mean,
            "gdp_std": gdp_std,
            "gdp_min": gdp_min,
            "gdp_max": gdp_max,
            "corr_gdp_inflation": r,
        },
        "series": {"years": years, "gdp": gdp, "inflation": infl},
        "yoy": {"years": yoy_years, "gdp": yoy_gdp, "inflation": yoy_infl, "summary": {"positive": pos, "negative": neg, "zero": zero}},
        "decades": {"labels": dec_labels, "gdp_mean": dec_g_mean, "infl_mean": dec_i_mean},
        "rolling": {"window": window, "years": roll_years, "gdp_ma": roll_gdp_ma, "infl_ma": roll_infl_ma, "infl_std": roll_infl_std},
        "extra": {"infl_hist_centers": hist_centers, "infl_hist_counts": hist_counts_, "cum_gdp": cum},
        "regression": {"slope": m, "intercept": b, "x_min": x_min, "x_max": x_max},
        "apartheid": apartheid,
        "extremes": extremes,
    }
    return JsonResponse(payload)

def datasets_list_api(request: HttpRequest) -> JsonResponse:
    # Small helper if you want a list endpoint too
    return JsonResponse({
        "ok": True,
        "datasets": [
            {"key": "gdp", "title": "GDP (South Africa)", "file": GDP_FILE.name},
            {"key": "inflation", "title": "Inflation (South Africa)", "file": INFL_FILE.name},
        ],
    })

def dataset_api(request: HttpRequest) -> JsonResponse:
    """
    ?name=gdp|inflation&limit=20
    Returns meta + a small (year,value) preview for the selected dataset.
    """
    name = (request.GET.get("name") or "gdp").lower()
    limit = int(request.GET.get("limit") or 20)
    if name not in ("gdp", "inflation"):
        return JsonResponse({"ok": False, "error": "Unknown dataset"}, status=400)

    path = GDP_FILE if name == "gdp" else INFL_FILE
    years, values, meta = load_country_series(path, COUNTRY)
    rows = [{"year": y, "value": v} for y, v in zip(years, values) if v is not None][:limit]
    return JsonResponse({
        "ok": True,
        "name": name,
        "title": "GDP (South Africa)" if name == "gdp" else "Inflation (South Africa)",
        "meta": meta,
        "columns": ["year", "value"],
        "rows": rows,
    })

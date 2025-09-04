from django.shortcuts import render

# analysis/views.py
from decimal import Decimal
import csv
from io import TextIOWrapper
from typing import Dict, Any

from django.contrib import messages
from django.db import transaction, models  # models imported so models.F and functions work
from django.db.models import (
    Avg, Max, Min, Count, Case, When, CharField, F
)
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import EconomicIndicatorForm
from .models import (
    EconomicIndicator, VolatilityAnalysis, BricsComparison, StatisticalSummary
)

# ---------------- Home / visualization page (your existing page) ----------------
def dashboard(request):
    return render(request, 'home/dashboard.html')

# ---------------- JSON endpoints (unchanged) ----------------
def apartheid_comparison(request):
    qs = EconomicIndicator.objects.values("era").annotate(
        years_count=Count("id"),
        mean_gdp=Avg("gdp_zar_bn"),
        mean_inflation=Avg("inflation_rate"),
        best_gdp=Max("gdp_zar_bn"),
        worst_gdp=Min("gdp_zar_bn"),
    ).order_by("era")
    return JsonResponse(list(qs), safe=False)

def high_volatility_years(request):
    qs = (
        VolatilityAnalysis.objects.filter(volatility_flag=True)
        .select_related("indicator")
        .values(
            year=F("indicator__year"),
            gdp_yoy_change=F("gdp_yoy_change"),
            inflation_yoy_change=F("inflation_yoy_change"),
            notes=F("notes"),
            gdp_zar_bn=F("indicator__gdp_zar_bn"),
            era=F("indicator__era"),
        )
        .order_by("indicator__year")
    )
    return JsonResponse(list(qs), safe=False)

def performance_summary(request):
    growth_category = Case(
        When(gdp_yoy_change__gt=3, then=models.Value("High Growth")),
        When(gdp_yoy_change__gte=0, gdp_yoy_change__lte=3, then=models.Value("Moderate Growth")),
        default=models.Value("Recession/Decline"),
        output_field=CharField(),
    )
    inflation_category = Case(
        When(inflation_rate__lt=3, then=models.Value("Low Inflation")),
        When(inflation_rate__gte=3, inflation_rate__lte=6, then=models.Value("Target Range")),
        default=models.Value("High Inflation"),
        output_field=CharField(),
    )
    qs = EconomicIndicator.objects.values("year", "gdp_zar_bn", "inflation_rate", "era").annotate(
        growth_category=growth_category,
        inflation_category=inflation_category,
    ).order_by("year")
    return JsonResponse(list(qs), safe=False)

def recent_trends(request):
    qs = EconomicIndicator.objects.filter(year__gte=2013).values(
        "year", "gdp_zar_bn", "inflation_rate", "gdp_yoy_change"
    ).order_by("-year")
    return JsonResponse(list(qs), safe=False)

def outlier_years(request):
    qs = VolatilityAnalysis.objects.filter(is_outlier=True).values(
        year=F("indicator__year"),
        gdp_yoy_change=F("gdp_yoy_change"),
        inflation_yoy_change=F("inflation_yoy_change"),
        notes=F("notes"),
    ).order_by("indicator__year")
    return JsonResponse(list(qs), safe=False)

def avg_by_era(request):
    qs = EconomicIndicator.objects.values("era").annotate(
        avg_gdp=models.functions.Round(Avg("gdp_zar_bn"), 2),
        avg_inflation=models.functions.Round(Avg("inflation_rate"), 2),
    )
    return JsonResponse(list(qs), safe=False)

# ---------------- helpers shared by dashboard & panel ----------------
def era_for_year(year: int) -> str:
    return "Post-Apartheid" if year >= 1994 else "Apartheid"

def _growth_label(v):
    if v is None: return "Unknown"
    if v > 3: return "High Growth"
    if Decimal('0') <= v <= 3: return "Moderate Growth"
    return "Recession/Decline"

def _inflation_label(v):
    if v is None: return "Unknown"
    if v < 3: return "Low Inflation"
    if 3 <= v <= 6: return "Target Range"
    return "High Inflation"

def _csv_response(filename: str) -> HttpResponse:
    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp

def build_database_context(request) -> Dict[str, Any]:
    year_q = request.GET.get('year')
    indicators_qs = EconomicIndicator.objects.order_by('year')
    search_row = None

    if year_q:
        try:
            y = int(year_q)
            search_row = EconomicIndicator.objects.filter(year=y).first()
            if search_row:
                indicators_qs = indicators_qs.filter(year=y)
            else:
                messages.warning(request, f"No record found for year {y}.")
        except ValueError:
            messages.error(request, "Year must be a number (e.g. 2010).")

    indicators = list(indicators_qs)
    perf = {ei.year: (_growth_label(ei.gdp_yoy_change), _inflation_label(ei.inflation_rate)) for ei in indicators}

    kpi_era = EconomicIndicator.objects.values('era').annotate(
        years_count=Count('id'),
        mean_gdp=Avg('gdp_zar_bn'),
        mean_inflation=Avg('inflation_rate'),
        best_gdp=Max('gdp_zar_bn'),
        worst_gdp=Min('gdp_zar_bn'),
    ).order_by('era')

    volatility = (
        VolatilityAnalysis.objects
            .filter(volatility_flag=True)
            .select_related('indicator')
            .annotate(
                year=F('indicator__year'),
                gdp_zar_bn=F('indicator__gdp_zar_bn'),
                era=F('indicator__era'),
            )
            .values('year','gdp_yoy_change','inflation_yoy_change','notes','gdp_zar_bn','era')
            .order_by('indicator__year')
    )

    brics = BricsComparison.objects.order_by('period_type', 'start_year')
    stats = StatisticalSummary.objects.order_by('indicator')

    best = EconomicIndicator.objects.filter(
        gdp_zar_bn=EconomicIndicator.objects.aggregate(Max('gdp_zar_bn'))['gdp_zar_bn__max']
    ).values('year','gdp_zar_bn','inflation_rate','era')
    worst = EconomicIndicator.objects.filter(
        gdp_zar_bn=EconomicIndicator.objects.aggregate(Min('gdp_zar_bn'))['gdp_zar_bn__min']
    ).values('year','gdp_zar_bn','inflation_rate','era')

    recent = EconomicIndicator.objects.filter(year__gte=2013).values(
        'year','gdp_zar_bn','inflation_rate','gdp_yoy_change'
    ).order_by('-year')
    avg_by_era = EconomicIndicator.objects.values('era').annotate(
        avg_gdp=Avg('gdp_zar_bn'),
        avg_inflation=Avg('inflation_rate'),
    ).order_by('era')

    return {
        'indicators': indicators,
        'perf': perf,
        'kpi_era': kpi_era,
        'volatility': volatility,
        'brics': brics,
        'stats': stats,
        'best': list(best),
        'worst': list(worst),
        'recent': list(recent),
        'avg_by_era': list(avg_by_era),
        'form': EconomicIndicatorForm(),
        'year_q': year_q or "",
        'search_row': search_row,
    }

# ---------------- HTML pages ----------------
def database_dashboard(request):
    # standalone database page
    ctx = build_database_context(request)
    return render(request, 'analysis/database.html', ctx)

def database_panel(request):
    # fragment that we embed in your Visualization page
    ctx = build_database_context(request)
    return render(request, 'analysis/database_panel.html', ctx)

# ---------------- CRUD ----------------
@transaction.atomic
def indicator_create(request):
    if request.method != 'POST':
        return redirect('database_dashboard')
    form = EconomicIndicatorForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Record added.")
    else:
        messages.error(request, f"Add failed: {form.errors}")
    return redirect('database_dashboard')

@transaction.atomic
def indicator_update(request, year):
    obj = get_object_or_404(EconomicIndicator, year=year)
    if request.method == 'POST':
        form = EconomicIndicatorForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Record updated.")
            return redirect('database_dashboard')
        messages.error(request, f"Update failed: {form.errors}")
    else:
        form = EconomicIndicatorForm(instance=obj)
    return render(request, 'analysis/indicator_edit.html', {'form': form, 'obj': obj})

@transaction.atomic
def indicator_delete(request, year):
    if request.method == 'POST':
        VolatilityAnalysis.objects.filter(indicator__year=year).delete()
        EconomicIndicator.objects.filter(year=year).delete()
        messages.success(request, f"Deleted records for {year}.")
    return redirect('database_dashboard')

# ---------------- Chart JSON ----------------
def series_economic(request):
    qs = EconomicIndicator.objects.order_by('year').values('year','gdp_zar_bn','inflation_rate')
    years = [r['year'] for r in qs]
    gdp = [float(r['gdp_zar_bn']) for r in qs]
    infl = [float(r['inflation_rate']) for r in qs]
    return JsonResponse({'years': years, 'gdp': gdp, 'inflation': infl})

# ---------------- CSV export ----------------
def export_economic_csv(request):
    resp = _csv_response('economic_indicators.csv')
    w = csv.writer(resp)
    w.writerow(['year','gdp_zar_bn','inflation_rate','gdp_yoy_change','inflation_yoy_change','era'])
    for r in EconomicIndicator.objects.order_by('year').values_list(
            'year','gdp_zar_bn','inflation_rate','gdp_yoy_change','inflation_yoy_change','era'):
        w.writerow(r)
    return resp

def export_volatility_csv(request):
    resp = _csv_response('volatility_analysis.csv')
    w = csv.writer(resp)
    w.writerow(['year','gdp_yoy_change','inflation_yoy_change','volatility_flag','is_outlier','notes'])
    qs = (VolatilityAnalysis.objects.select_related('indicator')
          .order_by('indicator__year')
          .values_list('indicator__year','gdp_yoy_change','inflation_yoy_change','volatility_flag','is_outlier','notes'))
    for r in qs: w.writerow(r)
    return resp

def export_brics_csv(request):
    resp = _csv_response('brics_comparison.csv')
    w = csv.writer(resp)
    w.writerow(['period_type','start_year','end_year','mean_gdp_zar_bn','median_inflation',
                'gdp_range_min','gdp_range_max','inflation_mode','insights'])
    for r in BricsComparison.objects.order_by('start_year').values_list(
            'period_type','start_year','end_year','mean_gdp_zar_bn','median_inflation',
            'gdp_range_min','gdp_range_max','inflation_mode','insights'):
        w.writerow(r)
    return resp

def export_stats_csv(request):
    resp = _csv_response('statistical_summary.csv')
    w = csv.writer(resp)
    w.writerow(['indicator','mean_value','median_value','std_dev','min_value','max_value','sample_size'])
    for r in StatisticalSummary.objects.order_by('indicator').values_list(
            'indicator','mean_value','median_value','std_dev','min_value','max_value','sample_size'):
        w.writerow(r)
    return resp

def export_performance_summary_csv(request):
    resp = _csv_response('performance_summary.csv')
    w = csv.writer(resp)
    w.writerow(['year','gdp_zar_bn','inflation_rate','era','growth_category','inflation_category'])
    for ei in EconomicIndicator.objects.order_by('year'):
        w.writerow([ei.year, ei.gdp_zar_bn, ei.inflation_rate, ei.era,
                    _growth_label(ei.gdp_yoy_change), _inflation_label(ei.inflation_rate)])
    return resp

# ---------------- CSV import ----------------
@transaction.atomic
def import_csv(request):
    if request.method != 'POST' or 'csv_file' not in request.FILES:
        return redirect('database_dashboard')

    model = request.POST.get('target_model')  # 'economic' | 'volatility' | 'brics' | 'stats'
    wrapper = TextIOWrapper(request.FILES['csv_file'].file, encoding=request.encoding or 'utf-8')
    reader = csv.DictReader(wrapper)

    def _dec(v):
        return None if v in (None,'','NULL','null') else Decimal(v.replace(',', '.'))

    def _bool(v):
        if isinstance(v, bool): return v
        s = (v or '').strip().lower()
        return s in ('1','true','t','yes','y')

    try:
        if model == 'economic':
            need = {'year','gdp_zar_bn','inflation_rate','gdp_yoy_change','inflation_yoy_change'}
            if not need.issubset(reader.fieldnames or []):
                raise ValueError("Economic CSV must have: year,gdp_zar_bn,inflation_rate,gdp_yoy_change,inflation_yoy_change[,era]")
            for row in reader:
                year = int(row['year'])
                era = row.get('era') or era_for_year(year)
                EconomicIndicator.objects.update_or_create(
                    year=year,
                    defaults=dict(
                        gdp_zar_bn=_dec(row['gdp_zar_bn']),
                        inflation_rate=_dec(row['inflation_rate']),
                        gdp_yoy_change=_dec(row['gdp_yoy_change']),
                        inflation_yoy_change=_dec(row['inflation_yoy_change']),
                        era=era,
                    )
                )

        elif model == 'volatility':
            need = {'year','gdp_yoy_change','inflation_yoy_change','volatility_flag','is_outlier','notes'}
            if not need.issubset(reader.fieldnames or []):
                raise ValueError(f"Volatility CSV must have headers: {sorted(need)}")
            for row in reader:
                ind = EconomicIndicator.objects.get(year=int(row['year']))
                VolatilityAnalysis.objects.update_or_create(
                    indicator=ind,
                    defaults=dict(
                        gdp_yoy_change=_dec(row['gdp_yoy_change']),
                        inflation_yoy_change=_dec(row['inflation_yoy_change']),
                        volatility_flag=_bool(row['volatility_flag']),
                        is_outlier=_bool(row['is_outlier']),
                        notes=row.get('notes',''),
                    )
                )

        elif model == 'brics':
            need = {'period_type','start_year','end_year','mean_gdp_zar_bn','median_inflation',
                    'gdp_range_min','gdp_range_max','inflation_mode','insights'}
            if not need.issubset(reader.fieldnames or []):
                raise ValueError(f"BRICS CSV must have headers: {sorted(need)}")
            for row in reader:
                BricsComparison.objects.update_or_create(
                    period_type=row['period_type'],
                    start_year=int(row['start_year']),
                    end_year=int(row['end_year']),
                    defaults=dict(
                        mean_gdp_zar_bn=_dec(row['mean_gdp_zar_bn']),
                        median_inflation=_dec(row['median_inflation']),
                        gdp_range_min=_dec(row['gdp_range_min']),
                        gdp_range_max=_dec(row['gdp_range_max']),
                        inflation_mode=_dec(row['inflation_mode']),
                        insights=row.get('insights',''),
                    )
                )

        elif model == 'stats':
            need = {'indicator','mean_value','median_value','std_dev','min_value','max_value','sample_size'}
            if not need.issubset(reader.fieldnames or []):
                raise ValueError(f"Statistical Summary CSV must have headers: {sorted(need)}")
            for row in reader:
                StatisticalSummary.objects.update_or_create(
                    indicator=row['indicator'],
                    defaults=dict(
                        mean_value=_dec(row['mean_value']),
                        median_value=_dec(row['median_value']),
                        std_dev=_dec(row['std_dev']),
                        min_value=_dec(row['min_value']),
                        max_value=_dec(row['max_value']),
                        sample_size=int(row['sample_size']) if row.get('sample_size') else None,
                    )
                )
        else:
            raise ValueError("Unknown target model for import.")

        messages.success(request, "CSV import completed successfully.")
    except Exception as e:
        transaction.set_rollback(True)
        messages.error(request, f"CSV import failed: {e}")

    return redirect('database_dashboard')
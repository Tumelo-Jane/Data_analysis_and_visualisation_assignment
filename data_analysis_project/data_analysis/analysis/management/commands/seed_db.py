
# analysis/management/commands/seed_db.py
from django.core.management.base import BaseCommand
from decimal import Decimal
from io import StringIO
import csv

from analysis.models import (
    EconomicIndicator,
    VolatilityAnalysis,
    BricsComparison,
    StatisticalSummary,
)

def era_for_year(year: int) -> str:
    return "Post-Apartheid" if year >= 1994 else "Apartheid"

# PASTE your full 1961–2023 dataset here as CSV.
# Decimals can be with dots or commas; we normalize commas -> dots.
# You can leave "era" empty; we'll infer it from the year.
EMBEDDED_ECONOMIC_CSV = """year,gdp_zar_bn,inflation_rate,gdp_yoy_change,inflation_yoy_change,era

1961,3.844734,2.102374,3.844734,2.102374,
1962,6.177931,1.246285,6.177931,1.246285,
1963,7.373709,1.337970,7.373709,1.337970,
1964,7.939609,2.534973,7.939609,2.534973,
1965,6.122798,4.069029,6.122798,4.069029,
1966,4.438386,3.489234,4.438386,3.489234,
1967,7.196523,3.538992,7.196523,3.538992,
1968,4.153373,1.986136,4.153373,1.986136,
1969,4.715903,3.238225,4.715903,3.238225,
1970,5.248661,4.991877,5.248661,4.991877,
1971,4.278934,5.957398,4.278934,5.957398,
1972,1.654830,6.425708,1.654830,6.425708,
1973,4.571945,9.433987,4.571945,9.433987,
1974,6.111122,11.724126,6.111122,11.724126,
1975,1.695434,13.425942,1.695434,13.425942,
1976,2.249860,11.020391,2.249860,11.020391,
1977,-0.093979,11.151964,-0.093979,11.151964,
1978,3.014480,11.135608,3.014480,11.135608,
1979,3.790519,13.293659,3.790519,13.293659,
1980,6.620583,13.660241,6.620583,13.660241,
1981,5.360791,15.254244,5.360791,15.254244,
1982,-0.383419,14.639032,-0.383419,14.639032,
1983,-1.846558,12.303207,-1.846558,12.303207,
1984,5.099152,11.526481,5.099152,11.526481,
1985,-1.211541,16.294227,-1.211541,16.294227,
1986,0.017849,18.654919,0.017849,18.654919,
1987,2.100729,16.160581,2.100729,16.160581,
1988,4.200110,12.779545,4.200110,12.779545,
1989,2.394795,14.730918,2.394795,14.730918,
1990,-0.317760,14.320956,-0.317760,14.320956,
1991,-1.018245,15.334802,-1.018245,15.334802,
1992,-2.137033,13.874680,-2.137033,13.874680,
1993,1.233558,9.717467,1.233558,9.717467,
1994,3.200000,8.938525,3.200000,8.938525,
1995,3.100000,8.680444,3.100000,8.680444,
1996,4.300000,7.354113,4.300000,7.354113,
1997,2.600000,8.597783,2.600000,8.597783,
1998,0.500000,6.880546,0.500000,6.880546,
1999,2.400000,5.181493,2.400000,5.181493,
2000,4.200000,5.338951,4.200000,5.338951,
2001,2.700000,5.701900,2.700000,5.701900,
2002,3.700374,9.494711,3.700374,9.494711,
2003,2.949075,5.679418,2.949075,5.679418,
2004,4.554560,-0.692030,4.554560,-0.692030,
2005,5.277052,2.062846,5.277052,2.062846,
2006,5.603806,3.243908,5.603806,3.243908,
2007,5.360474,6.177807,5.360474,6.177807,
2008,3.191044,10.074576,3.191044,10.074576,
2009,-1.538089,7.215314,-1.538089,7.215314,
2010,3.039733,4.089730,3.039733,4.089730,
2011,3.168556,4.999267,3.168556,4.999267,
2012,2.396232,5.724658,2.396232,5.724658,
2013,2.485468,5.784469,2.485468,5.784469,
2014,1.413826,6.129838,1.413826,6.129838,
2015,1.321862,4.540642,1.321862,4.540642,
2016,0.664552,6.571396,0.664552,6.571396,
2017,1.157947,5.184247,1.157947,5.184247,
2018,1.556784,4.517165,1.556784,4.517165,
2019,0.259936,4.120246,0.259936,4.120246,
2020,-6.168918,3.210036,-6.168918,3.210036,
2021,4.955033,4.611672,4.955033,4.611672,
2022,1.911480,7.039727,1.911480,7.039727,
2023,0.698485,6.073909,0.698485,6.073909,

"""

class Command(BaseCommand):
    help = "Seed database with economic data (embedded CSV), plus Volatility, BRICS, and Statistical Summary."

    def handle(self, *args, **kwargs):
        # Reset tables so seeding is deterministic
        VolatilityAnalysis.objects.all().delete()
        EconomicIndicator.objects.all().delete()
        BricsComparison.objects.all().delete()
        StatisticalSummary.objects.all().delete()

        # ---------- Economic Indicators from embedded CSV ----------
        # strip comments & blanks
        content_lines = [
            line for line in EMBEDDED_ECONOMIC_CSV.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        reader = csv.DictReader(StringIO("\n".join(content_lines)))

        need = {"year","gdp_zar_bn","inflation_rate","gdp_yoy_change","inflation_yoy_change","era"}
        if not reader.fieldnames or set(reader.fieldnames) != need:
            self.stdout.write(self.style.ERROR(
                "Embedded CSV header must be exactly:\n"
                "year,gdp_zar_bn,inflation_rate,gdp_yoy_change,inflation_yoy_change,era"
            ))
            return

        def dec(val):
            if val is None:
                return None
            s = str(val).strip()
            if s == "" or s.lower() in ("null","none"):
                return None
            # normalize decimal comma to dot
            s = s.replace(",", ".")
            return Decimal(s)

        added = 0
        for row in reader:
            try:
                year = int(row["year"])
            except Exception:
                continue
            era = row.get("era") or era_for_year(year)
            EconomicIndicator.objects.update_or_create(
                year=year,
                defaults=dict(
                    gdp_zar_bn=dec(row["gdp_zar_bn"]),
                    inflation_rate=dec(row["inflation_rate"]),
                    gdp_yoy_change=dec(row["gdp_yoy_change"]),
                    inflation_yoy_change=dec(row["inflation_yoy_change"]),
                    era=era,
                ),
            )
            added += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded EconomicIndicator rows: {added}"))

        # ---------- Volatility (sample — expand if you have more) ----------
        vol_rows = [
            (2008, "-1.23", "2.34", True, True, "Global Financial Crisis impact"),
            (2020, "-2.45", "3.21", True, True, "COVID-19 pandemic impact"),
            (2016, "0.56", "-1.78", False, False, "Stable growth period"),
            (1985, "-2.10", "4.20", True, True, "Apartheid era instability"),
            (2007, "5.60", "1.80", False, False, "Pre-crisis peak"),
        ]
        for y, gdp_yoy, infl_yoy, flag, outlier, notes in vol_rows:
            ind = EconomicIndicator.objects.filter(year=y).first()
            if not ind:
                continue
            VolatilityAnalysis.objects.update_or_create(
                indicator=ind,
                defaults=dict(
                    gdp_yoy_change=Decimal(gdp_yoy.replace(",", ".")),
                    inflation_yoy_change=Decimal(infl_yoy.replace(",", ".")),
                    volatility_flag=flag,
                    is_outlier=outlier,
                    notes=notes,
                ),
            )

        # ---------- BRICS (kept) ----------
        BricsComparison.objects.create(
            period_type="pre-brics",
            start_year=1994, end_year=2009,
            mean_gdp_zar_bn=Decimal("2345.67"),
            median_inflation=Decimal("6.78"),
            gdp_range_min=Decimal("1234.56"),
            gdp_range_max=Decimal("3456.78"),
            inflation_mode=Decimal("7.00"),
            insights="GDP growth improved post-BRICS, inflation mixed",
        )
        BricsComparison.objects.create(
            period_type="post-brics",
            start_year=2010, end_year=2022,
            mean_gdp_zar_bn=Decimal("4567.89"),
            median_inflation=Decimal("4.56"),
            gdp_range_min=Decimal("3456.78"),
            gdp_range_max=Decimal("5678.90"),
            inflation_mode=Decimal("4.00"),
            insights="Higher GDP levels, more stable inflation post-BRICS membership",
        )

        # ---------- Statistical Summary (kept) ----------
        StatisticalSummary.objects.create(
            indicator="GDP (ZAR bn)", mean_value="3456.78", median_value="3400.00",
            std_dev="789.12", min_value="987.65", max_value="5678.90", sample_size=63
        )
        StatisticalSummary.objects.create(
            indicator="Inflation (%)", mean_value="6.78", median_value="6.50",
            std_dev="2.34", min_value="2.00", max_value="12.34", sample_size=63
        )

        self.stdout.write(self.style.SUCCESS("Seeded database successfully."))

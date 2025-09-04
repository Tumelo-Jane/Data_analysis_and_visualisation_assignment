
from decimal import Decimal
from django.db import transaction
from analysis.models import EconomicIndicator, VolatilityAnalysis

@transaction.atomic
def add_economic_data(*, year: int, gdp: Decimal, inflation: Decimal, era: str):
    obj, created = EconomicIndicator.objects.get_or_create(
        year=year,
        defaults={"gdp_zar_bn": gdp, "inflation_rate": inflation, "era": era},
    )
    if not created:
        # if exists, we choose to raise to mimic MySQL proc strictness
        raise ValueError(f"EconomicIndicator for {year} already exists")
    return obj

@transaction.atomic
def update_economic_data(*, year: int, gdp: Decimal, inflation: Decimal):
    obj = EconomicIndicator.objects.select_for_update().get(year=year)
    obj.gdp_zar_bn = gdp
    obj.inflation_rate = inflation
    obj.save(update_fields=["gdp_zar_bn", "inflation_rate"])
    return obj

@transaction.atomic
def delete_economic_data(*, year: int):
    # delete “related” rows first (volatility), then indicator
    VolatilityAnalysis.objects.filter(indicator__year=year).delete()
    EconomicIndicator.objects.filter(year=year).delete()



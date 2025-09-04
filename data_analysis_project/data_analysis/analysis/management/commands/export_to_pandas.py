
from django.core.management.base import BaseCommand
import pandas as pd
from analysis.models import EconomicIndicator, VolatilityAnalysis

class Command(BaseCommand):
    help = "Load DB tables into Pandas and export CSVs"

    def handle(self, *args, **kwargs):
        ei = list(EconomicIndicator.objects.values())
        va = list(VolatilityAnalysis.objects.values(
            "indicator__year", "gdp_yoy_change", "inflation_yoy_change", "volatility_flag", "is_outlier", "notes"
        ))
        df_ei = pd.DataFrame(ei)
        df_va = pd.DataFrame(va).rename(columns={"indicator__year": "year"})

        df_ei.to_csv("economic_indicators.csv", index=False)
        df_va.to_csv("volatility_analysis.csv", index=False)

        self.stdout.write(self.style.SUCCESS(f"economic_indicators shape: {df_ei.shape}"))
        self.stdout.write(self.style.SUCCESS(f"volatility_analysis shape: {df_va.shape}"))


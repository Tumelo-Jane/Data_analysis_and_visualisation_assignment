
from django.db import models

class EconomicIndicator(models.Model):
    year = models.IntegerField(unique=True, db_index=True)
    gdp_zar_bn = models.DecimalField(max_digits=10, decimal_places=2)
    inflation_rate = models.DecimalField(max_digits=5, decimal_places=2)
    gdp_yoy_change = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    inflation_yoy_change = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    era = models.CharField(max_length=20, db_index=True)  # 'Apartheid' | 'Post-Apartheid'
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["year"]

    def __str__(self):
        return f"{self.year} | GDP {self.gdp_zar_bn} | CPI {self.inflation_rate}"


class VolatilityAnalysis(models.Model):
    indicator = models.OneToOneField(
        EconomicIndicator,
        to_field="year",
        db_column="year",
        on_delete=models.CASCADE,
        related_name="volatility",
    )
    gdp_yoy_change = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    inflation_yoy_change = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    volatility_flag = models.BooleanField(default=False, db_index=True)
    is_outlier = models.BooleanField(default=False)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def year(self):
        return self.indicator.year

    def __str__(self):
        return f"Volatility {self.year} (flag={self.volatility_flag}, outlier={self.is_outlier})"


class BricsComparison(models.Model):
    period_type = models.CharField(max_length=20)  # 'pre-brics' | 'post-brics'
    start_year = models.IntegerField()
    end_year = models.IntegerField()
    mean_gdp_zar_bn = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    median_inflation = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    gdp_range_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    gdp_range_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    inflation_mode = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    insights = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.period_type} {self.start_year}-{self.end_year}"


class StatisticalSummary(models.Model):
    indicator = models.CharField(max_length=50, db_index=True)
    mean_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    median_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    std_dev = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    min_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sample_size = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.indicator



# Create your models here.

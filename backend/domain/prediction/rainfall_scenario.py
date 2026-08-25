"""Which flood model a rainfall reading calls for.

A rule, not a fetch: it holds whether the app reads JAXA, a gauge, or a number
someone typed into the simulator.
"""

# PAGASA rainfall intensity classification.
HEAVY_RAIN_MM_HR = 30.0     # above this: intense — the 100-year model
MODERATE_RAIN_MM_HR = 7.5   # above this: moderate — the 25-year model


def scenario_for_intensity(value: float) -> str:
    """Map JAXA GSMaP rainfall intensity to CODEFISH return period scenario.
    Thresholds based on PAGASA rainfall intensity classification:
      Low:      < 7.5 mm/hr  → 5-year return period
      Moderate: 7.5–30 mm/hr → 25-year return period
      High:     > 30 mm/hr   → 100-year return period
    """
    if value > HEAVY_RAIN_MM_HR:
        return "100yr"
    elif value >= MODERATE_RAIN_MM_HR:
        return "25yr"
    return "5yr"

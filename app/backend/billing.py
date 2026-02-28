def compute_fixed_breakdown_for_day(fee_snapshot, days_in_month):
    fixed = fee_snapshot.get("fixed", {})
    daily_fees = fixed.get("daily", {}) if isinstance(fixed.get("daily"), dict) else {}
    monthly_fees = fixed.get("monthly", {}) if isinstance(fixed.get("monthly"), dict) else {}
    dph_multiplier = 1 + (fee_snapshot.get("dph_percent", 0) / 100.0)
    daily_with_dph = {key: value * dph_multiplier for key, value in daily_fees.items()}
    monthly_with_dph = {
        key: (value / days_in_month) * dph_multiplier for key, value in monthly_fees.items()
    }
    return daily_with_dph, monthly_with_dph


def validate_fundamentals(data):
    errors = []
    warnings = []

    revenue = data.get("annual_revenue")
    income = data.get("annual_net_income")
    ocf = data.get("annual_operating_cash_flow")
    capex = data.get("annual_capex")
    fcf = data.get("annual_free_cash_flow")

    def same_period(a, b):
        return (
            a is not None
            and b is not None
            and a.get("start") == b.get("start")
            and a.get("end") == b.get("end")
        )

    if not revenue or not income:
        errors.append("Missing revenue or net income")
    elif not same_period(revenue, income):
        errors.append("Revenue and income periods differ")

    if not ocf or not capex or not fcf:
        errors.append("Missing FCF components")
    elif not (
        same_period(ocf, capex)
        and same_period(ocf, fcf)
    ):
        errors.append("FCF periods differ")
    elif abs(
        fcf["value"] -
        (ocf["value"] - capex["value"])
    ) > 1:
        errors.append("FCF calculation mismatch")

    ttm_revenue = data.get("ttm_revenue")
    ttm_income = data.get("ttm_net_income")

    if not ttm_revenue or not ttm_income:
        warnings.append("Missing TTM data")
    elif ttm_revenue["end"] != ttm_income["end"]:
        errors.append("TTM periods differ")

    shares = data.get("shares_outstanding")
    if not shares or shares.get("value", 0) <= 0:
        errors.append("Invalid shares outstanding")
    else:
        warnings.append(
            "Share classes and dilution not yet verified"
        )

    if not data.get("verified", False):
        warnings.append(
            "Financial statements not independently verified"
        )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "valuation_ready": (
            len(errors) == 0
            and len(warnings) == 0
        ),
    }


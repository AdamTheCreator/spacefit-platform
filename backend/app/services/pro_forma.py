"""Pro Forma Calculator for commercial real estate acquisitions.

Pure financial math — no LLM needed. Uses Python Decimal for precision.
"""
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def _d(value: float | int | Decimal) -> Decimal:
    """Convert to Decimal."""
    return Decimal(str(value))


@dataclass
class ProFormaInputs:
    """Inputs for a pro forma analysis."""
    purchase_price: float
    cap_rate: float  # percentage, e.g. 7.0
    noi: float
    loan_to_value: float = 70.0  # percentage
    interest_rate: float = 6.5  # percentage
    loan_term_years: int = 10
    amortization_years: int = 30
    hold_period_years: int = 5
    exit_cap_rate: float = 7.5  # percentage
    rent_growth_rate: float = 2.5  # annual percentage
    expense_growth_rate: float = 2.0  # annual percentage
    vacancy_rate: float = 5.0  # percentage
    capex_reserve_psf: float = 0.50
    total_sf: int = 0
    closing_costs_pct: float = 2.0  # percentage of purchase price


@dataclass
class AnnualCashFlow:
    """Cash flow for a single year."""
    year: int
    gross_income: float
    vacancy_loss: float
    effective_income: float
    operating_expenses: float
    noi: float
    debt_service: float
    capex_reserve: float
    net_cash_flow: float
    cash_on_cash: float  # percentage


@dataclass
class ProFormaResult:
    """Complete pro forma analysis result."""
    # Summary metrics
    purchase_price: float
    total_equity: float
    loan_amount: float
    going_in_cap_rate: float
    exit_cap_rate: float

    # Returns
    unlevered_irr: float  # percentage
    levered_irr: float  # percentage
    equity_multiple: float
    avg_cash_on_cash: float  # percentage

    # Exit
    exit_value: float
    exit_noi: float
    net_sale_proceeds: float
    total_profit: float

    # Annual detail
    annual_cash_flows: list[AnnualCashFlow]

    def to_dict(self) -> dict[str, Any]:
        return {
            "purchase_price": self.purchase_price,
            "total_equity": self.total_equity,
            "loan_amount": self.loan_amount,
            "going_in_cap_rate": self.going_in_cap_rate,
            "exit_cap_rate": self.exit_cap_rate,
            "unlevered_irr": self.unlevered_irr,
            "levered_irr": self.levered_irr,
            "equity_multiple": self.equity_multiple,
            "avg_cash_on_cash": self.avg_cash_on_cash,
            "exit_value": self.exit_value,
            "exit_noi": self.exit_noi,
            "net_sale_proceeds": self.net_sale_proceeds,
            "total_profit": self.total_profit,
            "annual_cash_flows": [
                {
                    "year": cf.year,
                    "gross_income": cf.gross_income,
                    "vacancy_loss": cf.vacancy_loss,
                    "effective_income": cf.effective_income,
                    "operating_expenses": cf.operating_expenses,
                    "noi": cf.noi,
                    "debt_service": cf.debt_service,
                    "capex_reserve": cf.capex_reserve,
                    "net_cash_flow": cf.net_cash_flow,
                    "cash_on_cash": cf.cash_on_cash,
                }
                for cf in self.annual_cash_flows
            ],
        }


def _calculate_annual_debt_service(
    loan_amount: Decimal,
    interest_rate: Decimal,
    amortization_years: int,
) -> Decimal:
    """Calculate annual debt service using standard amortization formula."""
    if loan_amount <= 0 or interest_rate <= 0:
        return Decimal("0")

    monthly_rate = interest_rate / _d(100) / _d(12)
    num_payments = _d(amortization_years * 12)

    # Monthly payment = P * [r(1+r)^n] / [(1+r)^n - 1]
    factor = (1 + monthly_rate) ** int(num_payments)
    monthly_payment = loan_amount * (monthly_rate * factor) / (factor - 1)

    return (monthly_payment * _d(12)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _calculate_irr(cash_flows: list[float], max_iterations: int = 1000) -> float:
    """Calculate IRR using Newton's method."""
    if not cash_flows or all(cf == 0 for cf in cash_flows):
        return 0.0

    # Initial guess
    rate = Decimal("0.10")

    for _ in range(max_iterations):
        npv = Decimal("0")
        npv_derivative = Decimal("0")

        for i, cf in enumerate(cash_flows):
            cf_d = _d(cf)
            discount = (1 + rate) ** i
            npv += cf_d / discount
            if i > 0:
                npv_derivative -= _d(i) * cf_d / ((1 + rate) ** (i + 1))

        if abs(npv_derivative) < Decimal("1e-10"):
            break

        new_rate = rate - npv / npv_derivative

        if abs(new_rate - rate) < Decimal("1e-8"):
            return float(new_rate * 100)

        rate = new_rate

    return float(rate * 100)


def calculate_pro_forma(inputs: ProFormaInputs) -> ProFormaResult:
    """Calculate a complete pro forma analysis.

    Args:
        inputs: Pro forma input parameters

    Returns:
        ProFormaResult with all calculated metrics
    """
    purchase_price = _d(inputs.purchase_price)
    noi = _d(inputs.noi)
    ltv = _d(inputs.loan_to_value) / _d(100)
    closing_costs = purchase_price * _d(inputs.closing_costs_pct) / _d(100)

    # Capital structure
    loan_amount = (purchase_price * ltv).quantize(Decimal("0.01"))
    total_equity = (purchase_price - loan_amount + closing_costs).quantize(Decimal("0.01"))

    # Debt service
    annual_debt_service = _calculate_annual_debt_service(
        loan_amount, _d(inputs.interest_rate), inputs.amortization_years
    )

    # Estimate gross income and expenses from NOI
    # NOI = Gross Income - Vacancy - Operating Expenses
    # Assume operating expense ratio of ~35% of gross income
    vacancy_rate = _d(inputs.vacancy_rate) / _d(100)
    expense_ratio = _d("0.35")
    # gross_income * (1 - vacancy_rate) * (1 - expense_ratio) = NOI
    effective_multiplier = (1 - vacancy_rate) * (1 - expense_ratio)
    gross_income_yr1 = (noi / effective_multiplier).quantize(Decimal("0.01")) if effective_multiplier > 0 else noi
    expenses_yr1 = (gross_income_yr1 * (1 - vacancy_rate) * expense_ratio).quantize(Decimal("0.01"))

    capex_reserve = _d(inputs.capex_reserve_psf) * _d(inputs.total_sf) if inputs.total_sf > 0 else Decimal("0")

    rent_growth = _d(inputs.rent_growth_rate) / _d(100)
    expense_growth = _d(inputs.expense_growth_rate) / _d(100)

    # Annual cash flows
    annual_cfs: list[AnnualCashFlow] = []
    levered_cash_flows = [float(-total_equity)]  # Year 0
    unlevered_cash_flows = [float(-(purchase_price + closing_costs))]

    current_gross = gross_income_yr1
    current_expenses = expenses_yr1

    for year in range(1, inputs.hold_period_years + 1):
        if year > 1:
            current_gross = (current_gross * (1 + rent_growth)).quantize(Decimal("0.01"))
            current_expenses = (current_expenses * (1 + expense_growth)).quantize(Decimal("0.01"))

        vacancy_loss = (current_gross * vacancy_rate).quantize(Decimal("0.01"))
        effective_income = current_gross - vacancy_loss
        year_noi = effective_income - current_expenses

        net_cash_flow = year_noi - annual_debt_service - capex_reserve
        coc = float((net_cash_flow / total_equity * 100).quantize(Decimal("0.01"))) if total_equity > 0 else 0

        annual_cfs.append(AnnualCashFlow(
            year=year,
            gross_income=float(current_gross),
            vacancy_loss=float(vacancy_loss),
            effective_income=float(effective_income),
            operating_expenses=float(current_expenses),
            noi=float(year_noi),
            debt_service=float(annual_debt_service),
            capex_reserve=float(capex_reserve),
            net_cash_flow=float(net_cash_flow),
            cash_on_cash=coc,
        ))

        levered_cash_flows.append(float(net_cash_flow))
        unlevered_cash_flows.append(float(year_noi - capex_reserve))

    # Exit value
    exit_noi = _d(annual_cfs[-1].noi) * (1 + rent_growth)  # Next year NOI for exit
    exit_cap = _d(inputs.exit_cap_rate) / _d(100)
    exit_value = (exit_noi / exit_cap).quantize(Decimal("0.01")) if exit_cap > 0 else Decimal("0")

    # Rough estimate of remaining loan balance (simplified)
    # For a more accurate calculation, we'd track amortization schedule
    years_amortized = inputs.hold_period_years
    remaining_balance_ratio = _d(1) - (_d(years_amortized) / _d(inputs.amortization_years))
    remaining_loan = (loan_amount * remaining_balance_ratio).quantize(Decimal("0.01"))

    selling_costs = (exit_value * _d("0.02")).quantize(Decimal("0.01"))  # 2% selling costs
    net_sale_proceeds = exit_value - remaining_loan - selling_costs

    # Add exit to cash flows
    levered_cash_flows[-1] += float(net_sale_proceeds)
    unlevered_cash_flows[-1] += float(exit_value - selling_costs)

    # Calculate returns
    total_levered_cash = sum(levered_cash_flows[1:])
    equity_multiple = float(total_levered_cash / float(total_equity)) if float(total_equity) > 0 else 0
    avg_coc = sum(cf.cash_on_cash for cf in annual_cfs) / len(annual_cfs) if annual_cfs else 0

    levered_irr = _calculate_irr(levered_cash_flows)
    unlevered_irr = _calculate_irr(unlevered_cash_flows)

    total_profit = float(net_sale_proceeds + sum(_d(cf.net_cash_flow) for cf in annual_cfs) - total_equity)

    return ProFormaResult(
        purchase_price=float(purchase_price),
        total_equity=float(total_equity),
        loan_amount=float(loan_amount),
        going_in_cap_rate=inputs.cap_rate,
        exit_cap_rate=inputs.exit_cap_rate,
        unlevered_irr=round(unlevered_irr, 2),
        levered_irr=round(levered_irr, 2),
        equity_multiple=round(equity_multiple, 2),
        avg_cash_on_cash=round(avg_coc, 2),
        exit_value=float(exit_value),
        exit_noi=float(exit_noi),
        net_sale_proceeds=float(net_sale_proceeds),
        total_profit=round(total_profit, 2),
        annual_cash_flows=annual_cfs,
    )

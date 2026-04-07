from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field
from fastmcp import FastMCP


class DCFInput(BaseModel):
    """
    Typed input for the core DCF calculation used by the Quant agent.
    """

    cash_flows: List[float] = Field(
        ..., description="Projected free cash flows by period (typically annual)."
    )
    discount_rate: float = Field(
        ..., description="Discount rate (e.g. WACC), expressed as a decimal, e.g. 0.1 for 10%."
    )
    terminal_growth_rate: float = Field(
        ..., description="Terminal growth rate for the Gordon Growth Model."
    )


class DCFResult(BaseModel):
    """
    Normalized DCF result passed through the shared state.
    """

    equity_value: float = Field(
        ..., description="Present value of projected cash flows plus discounted terminal value."
    )
    present_value_of_cash_flows: float = Field(
        ..., description="Present value of the explicit forecast period cash flows."
    )
    discounted_terminal_value: float = Field(
        ..., description="Present value of the terminal value component."
    )
    implied_upside_pct: Optional[float] = Field(
        default=None,
        description=(
            "Optional implied upside vs current market cap/price, if provided upstream."
        ),
    )


def run_dcf(dcf_input: DCFInput) -> DCFResult:
    """
    Core DCF implementation used inside the Python orchestration layer.

    This mirrors the logic of the MCP-exposed `calculate_dcf` tool but returns
    a strongly-typed `DCFResult` for internal use.
    """

    cash_flows = dcf_input.cash_flows
    r = dcf_input.discount_rate
    g = dcf_input.terminal_growth_rate

    discounted_flows: List[float] = []
    for t, cf in enumerate(cash_flows, start=1):
        discounted_flows.append(cf / ((1 + r) ** t))

    if not cash_flows:
        equity_value = 0.0
        discounted_terminal_value = 0.0
    else:
        last_cf = cash_flows[-1]
        terminal_value = (last_cf * (1 + g)) / (r - g)
        discounted_terminal_value = terminal_value / ((1 + r) ** len(cash_flows))
        equity_value = sum(discounted_flows) + discounted_terminal_value

    return DCFResult(
        equity_value=equity_value,
        present_value_of_cash_flows=sum(discounted_flows),
        discounted_terminal_value=discounted_terminal_value,
        implied_upside_pct=None,
    )


# MCP wrapper so the same logic can be called as a tool from other processes.

mcp = FastMCP("VALUATION-MODELS")


@mcp.tool
async def calculate_dcf(
    current_fcf: float,
    growth_rate: float,
    wacc: float,
    terminal_growth: float,
    years: int = 5,
) -> dict:
    """
    Calculates a multi-year Discounted Cash Flow (DCF) valuation using the same
    logic as `run_dcf`, exposed as an MCP tool.
    """

    projected_flows: List[float] = []
    temp_fcf = current_fcf
    for _ in range(years):
        temp_fcf *= 1 + growth_rate
        projected_flows.append(temp_fcf)

    dcf_input = DCFInput(
        cash_flows=projected_flows,
        discount_rate=wacc,
        terminal_growth_rate=terminal_growth,
    )
    result = run_dcf(dcf_input)

    return {
        "enterprise_value": round(result.equity_value, 2),
        "present_value_of_cash_flows": round(result.present_value_of_cash_flows, 2),
        "discounted_terminal_value": round(result.discounted_terminal_value, 2),
        "calculation_summary": f"DCF calculated over {years} years at {growth_rate*100:.2f}% growth.",
    }
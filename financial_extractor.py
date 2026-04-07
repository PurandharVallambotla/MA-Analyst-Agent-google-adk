from __future__ import annotations

import os
from typing import Dict, List, Optional, Any

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field


USER_AGENT = os.getenv("SEC_USER_AGENT", "M&A-Analyst/1.0")

# The SEC's "Company Facts" API is the gold standard for raw numbers
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


class FinancialPeriod(BaseModel):
    """
    Single-period snapshot of key US-GAAP metrics.
    """

    end_date: str = Field(..., description="Period end date as reported by SEC (YYYY-MM-DD).")
    revenue: Optional[float] = Field(default=None, description="Total revenues for the period.")
    net_income: Optional[float] = Field(default=None, description="Net income for the period.")
    operating_cash_flow: Optional[float] = Field(
        default=None, description="Net cash provided by operating activities."
    )


class FinancialMetrics(BaseModel):
    """
    Normalized financial metrics used by the Quant agent.
    """

    cik: str = Field(..., description="10-digit zero-padded CIK.")
    periods: List[FinancialPeriod] = Field(
        default_factory=list, description="Historical annual periods, most recent last."
    )

    @property
    def latest_period(self) -> Optional[FinancialPeriod]:
        return self.periods[-1] if self.periods else None


def _extract_latest_annual_usd(facts: Dict[str, Any], tag: str) -> Optional[Dict[str, Any]]:
    """Helper to get the latest 10-K USD fact for a given tag."""
    fact_data = facts.get(tag, {}).get("units", {}).get("USD", [])
    annuals = [f for f in fact_data if f.get("form") == "10-K"]
    if not annuals:
        return None
    # SEC data is usually chronological; take the last 10-K entry
    return annuals[-1]


def extract_financial_metrics(submissions: Dict[str, Any]) -> FinancialMetrics:
    """
    Pure-Python helper for the Quant agent.

    Given SEC submissions or a known CIK, fetches Company Facts and normalizes
    a small set of core US-GAAP metrics into `FinancialMetrics`.
    """

    cik = submissions.get("cik") or submissions.get("cik_str") or ""
    cik_str = str(cik).zfill(10)
    url = FACTS_URL.format(cik=cik_str)
    headers = {"User-Agent": USER_AGENT}

    with httpx.Client() as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        full_facts = response.json().get("facts", {}).get("us-gaap", {})

    metrics_to_find = {
        "revenue": "Revenues",
        "net_income": "NetIncomeLoss",
        "operating_cash_flow": "NetCashProvidedByUsedInOperatingActivities",
    }

    period = FinancialPeriod(
        end_date="",
        revenue=None,
        net_income=None,
        operating_cash_flow=None,
    )

    for label, tag in metrics_to_find.items():
        latest = _extract_latest_annual_usd(full_facts, tag)
        if latest:
            if not period.end_date:
                period.end_date = latest.get("end", "")
            value = latest.get("val")
            if label == "revenue":
                period.revenue = value
            elif label == "net_income":
                period.net_income = value
            elif label == "operating_cash_flow":
                period.operating_cash_flow = value

    return FinancialMetrics(cik=cik_str, periods=[period])


# ---------------------------------------------------------------------------
# MCP server wrapper (existing interface)
# ---------------------------------------------------------------------------

mcp = FastMCP("FINANCIAL-EXTRACTOR")


@mcp.tool
async def get_dcf_inputs(cik: str) -> dict:
    """
    Extracts core metrics for a DCF model: Revenue, Net Income, and Operating Cash Flow.

    This is a thin async wrapper around the synchronous extraction logic so that
    other processes can call it via MCP.
    """

    padded_cik = cik.zfill(10)
    url = FACTS_URL.format(cik=padded_cik)
    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        full_facts = response.json().get("facts", {}).get("us-gaap", {})

    metrics_to_find = {
        "revenue": "Revenues",
        "net_income": "NetIncomeLoss",
        "operating_cash_flow": "NetCashProvidedByUsedInOperatingActivities",
    }

    extracted_data = {}
    for label, tag in metrics_to_find.items():
        fact_data = full_facts.get(tag, {}).get("units", {}).get("USD", [])
        if fact_data:
            annuals = [f for f in fact_data if f.get("form") == "10-K"]
            if not annuals:
                continue
            latest_annual = annuals[-1]
            extracted_data[label] = {
                "value": latest_annual["val"],
                "end_date": latest_annual["end"],
            }

    return extracted_data
"""
Core orchestration logic for the Autonomous M&A Analyst.

This module defines a production-grade, sequential orchestration pattern for
three specialized agents:

- SourcingAgent:   maps a ticker or company name to a CIK and recent filings
- QuantAgent:      extracts financial metrics and runs a DCF valuation
- RiskAgent:       performs qualitative / quantitative risk checks

State is shared between agents via a Pydantic model to ensure that data passed
across steps is well-structured and validated. While this is not a full
LangGraph implementation, it mirrors the same ideas: a typed, shared state and
named nodes executed in sequence.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError

from google.adk.agents import Agent as AdkAgent, SequentialAgent as AdkSequentialAgent

from .tools import get_sec_mcp, get_search_mcp
from .dcf_tool import DCFInput, DCFResult, run_dcf
from .financial_extractor import FinancialMetrics, extract_financial_metrics


class MnaSharedState(BaseModel):
    """
    Shared state passed between Sourcing, Quant, and Risk agents.

    This mirrors the typed state pattern from LangGraph: each node receives a
    validated instance and returns an updated instance.
    """

    # Input identifiers
    ticker: str = Field(..., description="Public equity ticker symbol, e.g. AAPL")
    company_name: Optional[str] = Field(
        default=None, description="Optional company name override."
    )

    # Sourcing outputs
    cik: Optional[str] = Field(
        default=None, description="10-digit zero-padded SEC CIK for the company."
    )
    submissions: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Raw SEC EDGAR submissions/filings metadata for the company.",
    )

    # Quant outputs
    financials: Optional[FinancialMetrics] = Field(
        default=None,
        description="Parsed US-GAAP financial metrics extracted from SEC filings.",
    )
    dcf_input: Optional[DCFInput] = Field(
        default=None, description="Input assumptions used for DCF valuation."
    )
    dcf_result: Optional[DCFResult] = Field(
        default=None, description="Calculated DCF valuation result."
    )

    # Risk outputs
    risk_flags: List[str] = Field(
        default_factory=list, description="List of qualitative/quantitative risk flags."
    )
    risk_score: Optional[float] = Field(
        default=None,
        description="Aggregate risk score in [0, 1], where 1 is highest risk.",
        ge=0.0,
        le=1.0,
    )

    # Final recommendation
    recommendation: Optional[str] = Field(
        default=None,
        description="High-level recommendation string, e.g. 'BUY', 'NO-BUY', 'WATCHLIST'.",
    )

    # Debug / traceability
    notes: List[str] = Field(
        default_factory=list,
        description="Free-form trace messages to aid debugging and auditability.",
    )


class BaseAgent:
    """Lightweight base class for all agents in the system."""

    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, state: MnaSharedState) -> MnaSharedState:
        raise NotImplementedError


class SourcingAgent(BaseAgent):
    """
    Agent responsible for sourcing SEC data: CIK lookup and recent filings.
    """

    def __init__(self) -> None:
        super().__init__(name="sourcing_agent")

    def run(self, state: MnaSharedState) -> MnaSharedState:
        # Placeholder implementation; production pipeline uses ADK + MCP.
        return state


class QuantAgent(BaseAgent):
    """
    Agent responsible for extracting financial metrics and running valuation models.

    This pure-Python version is a lightweight placeholder – the production path
    runs via the ADK graph with MCP tools.
    """

    def __init__(self) -> None:
        super().__init__(name="quant_agent")

    def run(self, state: MnaSharedState) -> MnaSharedState:
        return state


class RiskAgent(BaseAgent):
    """
    Agent responsible for basic risk analysis given financials and valuation.

    This pure-Python version is a lightweight placeholder – the production path
    runs via the ADK graph with MCP tools.
    """

    def __init__(self) -> None:
        super().__init__(name="risk_agent")

    def run(self, state: MnaSharedState) -> MnaSharedState:
        return state


class SequentialOrchestrator:
    """
    Minimal sequential orchestration pattern inspired by LangGraph.

    Each node is a callable that takes a `MnaSharedState` and returns an
    updated instance. The orchestrator ensures that the state remains valid
    between steps.
    """

    def __init__(self, nodes: List[BaseAgent]) -> None:
        self.nodes = nodes

    def run(self, initial_state: MnaSharedState) -> MnaSharedState:
        state = initial_state
        for node in self.nodes:
            try:
                state = node.run(state)
                # Validate state after each step to catch subtle bugs early.
                state = MnaSharedState.model_validate(state)
            except ValidationError as exc:
                state.notes.append(
                    f"[orchestrator] Validation error in node {node.name}: {exc}"
                )
                break
        return state


def build_default_orchestrator() -> SequentialOrchestrator:
    """
    Factory that wires together the default tools and agents.

    This is the entry point most callers should use.
    """

    sourcing = SourcingAgent()
    quant = QuantAgent()
    risk = RiskAgent()

    return SequentialOrchestrator(nodes=[sourcing, quant, risk])


def run_mna_analyst(
    ticker: str,
    company_name: Optional[str] = None,
    initial_state_overrides: Optional[Dict[str, Any]] = None,
) -> MnaSharedState:
    """
    High-level entry point for the Autonomous M&A Analyst.

    This function builds the orchestrator, initializes the shared state, and
    runs the Sourcing → Quant → Risk pipeline.
    """

    base_state_kwargs: Dict[str, Any] = {
        "ticker": ticker,
        "company_name": company_name,
    }
    if initial_state_overrides:
        base_state_kwargs.update(initial_state_overrides)

    state = MnaSharedState(**base_state_kwargs)

    orchestrator = build_default_orchestrator()
    final_state = orchestrator.run(initial_state=state)
    return final_state


# ---------------------------------------------------------------------------
# Google ADK wiring (Sequential Orchestration Pattern)
# ---------------------------------------------------------------------------

# These definitions expose an ADK-native graph so that the same three-agent
# pipeline can run inside the Google Agent Developer Kit. The tools referenced
# here are MCP or HTTP tools registered in `tools.py`.


# --- 1. Sourcing Agent (ADK) ---
adk_sourcing_agent = AdkAgent(
    name="sourcing_agent",
    description="Retrieves official SEC filings and company identifiers.",
    instruction="""
    1. Given a ticker (and optional company name) from state, use the SEC MCP tool.
    2. Resolve the company's CIK and fetch recent submissions from EDGAR.
    3. Save 'cik', 'submissions', and 'ticker' into the shared session state.
    """,
    tools=[get_sec_mcp()],
)


# --- 2. Quant Agent (ADK) ---
adk_quant_agent = AdkAgent(
    name="quant_agent",
    description="Calculates valuation models (DCF) using financial data.",
    instruction="""
    1. Read 'cik' and 'submissions' from the shared state.
    2. Extract US-GAAP metrics (Revenue, Net Income) from SEC filings.
    3. Construct a DCF input and compute a base-case valuation.
    4. Save 'financials', 'dcf_input', and 'dcf_result' back to state.
    """,
    tools=[],
)


# --- 3. Risk Agent (ADK) ---
adk_risk_agent = AdkAgent(
    name="risk_agent",
    description="Scans for legal red flags, lawsuits, and negative news sentiment.",
    instruction="""
    1. Read 'ticker', 'company_name', and 'dcf_result' from state.
    2. Use the search tool to discover recent lawsuits, regulatory actions, or major news.
    3. Derive qualitative risk flags and a normalized risk_score in [0, 1].
    4. Combine valuation upside and risk_score into a final recommendation.
    5. Save 'risk_flags', 'risk_score', and 'recommendation' into state.
    """,
    tools=[get_search_mcp()],
)


# --- 4. Main Sequential Flow (ADK) ---
adk_mna_analyst_flow = AdkSequentialAgent(
    name="mna_analyst_flow",
    sub_agents=[adk_sourcing_agent, adk_quant_agent, adk_risk_agent],
)


# --- 5. Root Coordinator (ADK entrypoint) ---
root_agent = AdkAgent(
    name="root_agent",
    model="gemini-2.0-flash",
    sub_agents=[adk_mna_analyst_flow],
    description="Top-level M&A Analyst coordinator.",
    instruction="""
    You are the autonomous M&A lead.
    1. Delegate sourcing of SEC filings to the sourcing_agent.
    2. Delegate valuation to the quant_agent.
    3. Delegate risk analysis to the risk_agent.
    4. Synthesize all outputs into a final Buy / No-Buy recommendation with rationale.
    """,
)

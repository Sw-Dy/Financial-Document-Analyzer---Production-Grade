"""Production-grade financial analysis agents with structured outputs.

All agents are configured to:
- Output strictly in JSON format
- Cite document sources
- Provide deterministic financial analysis
- Maintain professional rigor
- Avoid hallucinations
"""

import os
import json
from dotenv import load_dotenv

load_dotenv()

from crewai import Agent
from langchain_openai import ChatOpenAI

### Loading LLM - Use lazy initialization to avoid API key errors at import time
_llm_instance = None


def get_llm():
    """Get LLM instance with lazy initialization"""
    global _llm_instance
    if _llm_instance is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        _llm_instance = ChatOpenAI(
            model="gpt-4",
            temperature=0.2,  # Lower temperature for consistency
            api_key=api_key,
        )
    return _llm_instance


# Graceful fallback for development
class DummyLLM:
    """Dummy LLM for development without API keys"""

    def __init__(self):
        self.model_name = "dummy"


try:
    llm = get_llm()
except Exception:
    print("Note: Using dummy LLM for development (set OPENAI_API_KEY to use real LLM)")
    try:
        llm = ChatOpenAI.__new__(ChatOpenAI)
        llm.model_name = "gpt-4"
    except:
        llm = DummyLLM()

# SENIOR EQUITY ANALYST AGENT
financial_analyst = Agent(
    role="Senior Equity Research Analyst",
    goal="""Conduct rigorous financial analysis of the provided document and output 
structured JSON with:
- Revenue trends and growth drivers
- Profitability metrics (margins, ROE)
- Cash flow quality and adequacy
- Identified financial risks
- Specific investment recommendation (BUY/HOLD/SELL)
- Confidence score (0-100)
- Cited evidence from the document""",
    backstory="""You are a senior equity analyst at a major investment firm with 15+ years 
of experience analyzing financial statements. You:
- Follow CFA Institute standards
- Require documentary evidence for all claims
- Quantify assertions with specific numbers from the document
- Assess both quantitative and qualitative factors
- Provide clear, defensible recommendations
- Explicitly cite the document sections supporting your analysis
- Avoid speculation and only use facts from the provided document""",
    tools=[],
    llm=llm,
    max_iter=3,
    max_rpm=1,
    allow_delegation=False,
    verbose=True,
    allow_code_execution=False,
)


# FINANCIAL RISK ASSESSMENT AGENT
risk_assessor = Agent(
    role="Financial Risk Assessment Specialist",
    goal="""Systematically assess all financial risks in the document including:
- Liquidity risks (working capital, cash conversion cycle)
- Solvency risks (debt levels, interest coverage, credit ratios)
- Operational risks (revenue concentration, margin volatility)
- Market risks (competitive position, industry dynamics)
- Regulatory or compliance risks
Return structured JSON with risk categories, severity (LOW/MEDIUM/HIGH), 
and specific mitigation recommendations based on document evidence.""",
    backstory="""You are a risk management specialist with expertise in financial analysis 
and risk quantification. You:
- Have handled portfolio analysis for institutional clients
- Understand both financial and operational risk drivers
- Quantify risks where possible
- Can identify hidden risks from financial statement patterns
- Cite specific evidence from documents
- Distinguish between manageable and critical risks
- Recommend specific, actionable risk mitigation strategies
- Only reference information explicitly in the provided document""",
    tools=[],
    llm=llm,
    max_iter=3,
    max_rpm=1,
    allow_delegation=False,
    verbose=True,
    allow_code_execution=False,
)


# CASH FLOW ANALYSIS AGENT
cash_flow_analyst = Agent(
    role="Cash Flow Quality Analyst",
    goal="""Perform detailed cash flow analysis and output JSON containing:
- Operating cash flow trends and quality
- Free cash flow adequacy for operations and investments
- Cash conversion efficiency (not just earnings quality)
- Debt service capability
- Capital allocation sustainability
- Red flags in cash generation vs. reported earnings
Include specific figures from the document and assess quality of earnings.""",
    backstory="""You are a financial analyst specializing in cash flow analysis and 
quality of earnings. You:
- Understand that earnings can be manipulated but cash flows are harder to fake
- Can identify mismatches between reported earnings and cash generation
- Assess working capital management effectiveness
- Evaluate capital expenditure trends
- Understand SG&A and capex sustainability
- Identify cash flow warning signs
- Only cite numbers directly from the provided financial documents
- Never speculate beyond what the document states""",
    tools=[],
    llm=llm,
    max_iter=3,
    max_rpm=1,
    allow_delegation=False,
    verbose=True,
    allow_code_execution=False,
)


# CONSOLIDATED RECOMMENDATION ENGINE AGENT
investment_strategist = Agent(
    role="Chief Investment Strategist",
    goal="""Synthesize analysis from all sources into a final JSON investment recommendation:
{
  "recommendation": "BUY|HOLD|SELL",
  "confidence_score": 0-100,
  "thesis_summary": "2-3 sentence conclusion",
  "key_strengths": ["list of key positives"],
  "key_risks": ["list of key negatives"],
  "price_target_upside": "x% estimated upside",
  "time_horizon": "3-12 months",
  "position_sizing": "Conservative|Moderate|Aggressive",
  "next_milestones": ["critical events to monitor"]
}
Base recommendation solely on evidence provided in the document.""",
    backstory="""You are the Chief Investment Officer making final asset allocation decisions. You:
- Synthesize diverse analytical perspectives into coherent investment theses
- Ensure recommendations are backed by specific evidence
- Weigh positive and negative factors quantitatively
- Understand portfolio construction principles
- Can clearly articulate investment rationale
- Provide specific, actionable guidance
- Never make recommendations without documentary evidence
- Only use information from provided financial documents""",
    tools=[],
    llm=llm,
    max_iter=2,
    max_rpm=1,
    allow_delegation=False,
    verbose=True,
    allow_code_execution=False,
)

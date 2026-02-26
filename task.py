## Importing libraries and files  
from crewai import Task

from agents import financial_analyst


## Creating a task to help solve user's query
analyze_financial_document = Task(
    description="Analyze the user's query: {query}\n\
Review the provided financial document carefully.\n\
Extract key financial metrics and indicators.\n\
Provide professional investment insights and analysis.",

    expected_output="""Provide a comprehensive financial analysis including:
- Key financial metrics identified
- Investment recommendations based on the document
- Risk assessment for the investment
- Market opportunities
- Professional summary with actionable insights""",

    agent=financial_analyst,
    tools=[],
    async_execution=False,
    output_file="outputs/analysis_result.md"
)
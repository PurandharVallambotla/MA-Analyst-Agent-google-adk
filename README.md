# MA-Analyst-Agent-google-adk
Autonomous M&amp;A Analyst Agent This project is a specialized AI agent built using the Google Agent Development Kit (ADK). It is designed to automate the financial analysis required for Mergers and Acquisitions (M&amp;A) by extracting data and performing Discounted Cash Flow (DCF) valuations.

📁 Project Structure

->agent.py: The core logic and orchestration of the AI agent.

->dcf_tool.py: Handles the financial modeling and intrinsic value calculations.

->financial_extractor.py: Logic for parsing financial statements and data points.

->sec_mcp_server.py: A Model Context Protocol (MCP) server to interface with SEC filings.

->tools.py: General utility functions used by the agent.

🚀 Features

->Automated Data Extraction: Pulls financial metrics directly from SEC filings.

->Financial Modeling: Performs automated DCF analysis to determine company valuation.

->Agentic Workflow: Uses a single-agent architecture to process complex financial queries.

🛠️ Setup

1.Clone the repository.

2.Install the Google ADK.

3.Create a .env file and add your credentials:
  Plaintext
  GOOGLE_API_KEY=your_key_here
  SEC_API_KEY=your_key_here

4.Run the agent:
  Bash
    python agent.py

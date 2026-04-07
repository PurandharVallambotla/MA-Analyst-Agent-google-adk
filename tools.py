import os
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StdioConnectionParams,
    StreamableHTTPConnectionParams,
)
from mcp import StdioServerParameters


# 1. SEC EDGAR TOOLSET (Local MCP Server)
# This connects to a local Python script that wraps the SEC's EDGAR API.
def get_sec_mcp():
    return MCPToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="python",
                args=["sec_mcp_server.py"],  # Your local MCP server script
                env={"SEC_USER_AGENT": os.getenv("SEC_USER_AGENT")},
            )
        )
    )


# 2. RISK SEARCH TOOLSET (Google Search MCP)
# Used for finding lawsuits, regulatory fines, and negative news sentiment.
def get_search_mcp():
    return MCPToolset(
        connection_params=StreamableHTTPConnectionParams(
            url="https://googlesearch.googleapis.com/mcp",
            headers={
                "X-Goog-Api-Key": os.getenv("GOOGLE_API_KEY"),
                "Content-Type": "application/json",
            },
        )
    )
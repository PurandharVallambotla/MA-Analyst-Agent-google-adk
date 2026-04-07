import os
import httpx
import diskcache #
from fastmcp import FastMCP

# 1. Initialize FastMCP and Cache
mcp = FastMCP("SEC-EDGAR")
# This creates a '.cache' folder in your project directory
cache = diskcache.Cache(".cache") #

# SEC requires a descriptive User-Agent
SEC_BASE_URL = "https://data.sec.gov/submissions"
USER_AGENT = os.getenv("SEC_USER_AGENT", "M&A-Analyst-Bot/1.0 (admin@example.com)")

@mcp.tool
async def get_company_submissions(cik: str) -> dict:
    """
    Fetches latest SEC submissions with a 24-hour cache.
    """
    padded_cik = cik.zfill(10)
    cache_key = f"submissions_{padded_cik}"
    
    # Check if we already have this data
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data

    url = f"{SEC_BASE_URL}/CIK{padded_cik}.json"
    headers = {"User-Agent": USER_AGENT}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json().get("filings", {}).get("recent", {})
        
        # Store in cache for 86,400 seconds (24 hours)
        cache.set(cache_key, data, expire=86400)
        return data

@mcp.tool
async def search_cik_by_ticker(ticker: str) -> str:
    """
    Converts ticker to CIK with a 7-day cache (tickers rarely change).
    """
    ticker_upper = ticker.upper()
    cache_key = f"ticker_{ticker_upper}"
    
    cached_cik = cache.get(cache_key)
    if cached_cik:
        return cached_cik

    url = "https://www.sec.gov/files/company_tickers.json"
    headers = {"User-Agent": USER_AGENT}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        ticker_data = response.json()
        
        for entry in ticker_data.values():
            if entry["ticker"].upper() == ticker_upper:
                cik = str(entry["cik"])
                # Cache for 7 days
                cache.set(cache_key, cik, expire=604800)
                return cik
        
        return f"Ticker {ticker} not found."

if __name__ == "__main__":
    mcp.run()
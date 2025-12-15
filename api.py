from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import asyncio
from main import GoogleMapsScraper

app = FastAPI()

class ScrapeRequest(BaseModel):
    urls: List[str]
    max_reviews: Optional[int] = None

@app.post("/scrape")
async def scrape_reviews(request: ScrapeRequest):
    results = {}
    scraper = GoogleMapsScraper()
    
    for url in request.urls:
        try:
            print(f"API: Starting scrape for {url} with limit {request.max_reviews}")
            reviews = await scraper.scrape(url, max_reviews=request.max_reviews)
            results[url] = {
                "status": "success",
                "count": len(reviews),
                "reviews": reviews
            }
        except Exception as e:
            print(f"API: Failed to scrape {url}: {e}")
            results[url] = {
                "status": "error",
                "error": str(e)
            }
            
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

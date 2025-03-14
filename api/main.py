from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import pytz
from scraper.tender_scraper import TenderScraper
import json
import os

app = FastAPI(
    title="Tenders Ville API",
    description="Mobile-optimized API for accessing Kenyan tender information",
    version="1.0.0"
)

# Enable CORS for mobile app access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this with your mobile app's domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize scraper
scraper = TenderScraper()

@app.get("/")
async def root():
    """Welcome endpoint with API information"""
    return {
        "name": "Tenders Ville API",
        "version": "1.0.0",
        "description": "Mobile-optimized tender information system",
        "docs_url": "/docs",
        "status": "online"
    }

@app.get("/tenders")
async def get_tenders(
    status: Optional[str] = Query(None, enum=["open", "closing_soon", "closed"]),
    entity: Optional[str] = None,
    category: Optional[str] = None,
    days_remaining: Optional[int] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
) -> Dict:
    """
    Get tenders with optional filters
    
    - **status**: Filter by tender status (open/closing_soon/closed)
    - **entity**: Filter by procuring entity name
    - **category**: Filter by tender category
    - **days_remaining**: Filter by days remaining until closing
    - **page**: Page number for pagination
    - **limit**: Number of items per page
    """
    try:
        # Get all tenders
        all_tenders = []
        
        # Get tenders from both sources
        mygov_tenders = scraper.scrape_mygov_tenders()
        ppip_tenders = scraper.scrape_ppip_tenders()
        all_tenders.extend(mygov_tenders)
        all_tenders.extend(ppip_tenders)
        
        # Apply filters
        filtered_tenders = all_tenders
        
        if status:
            filtered_tenders = [t for t in filtered_tenders if t.get('status') == status]
            
        if entity:
            entity = entity.lower()
            filtered_tenders = [
                t for t in filtered_tenders 
                if t.get('procuring_entity', '').lower().find(entity) != -1
            ]
            
        if category:
            category = category.lower()
            filtered_tenders = [
                t for t in filtered_tenders 
                if t.get('category', '').lower().find(category) != -1
            ]
            
        if days_remaining is not None:
            filtered_tenders = [
                t for t in filtered_tenders 
                if t.get('days_remaining') is not None and t.get('days_remaining') <= days_remaining
            ]
        
        # Calculate pagination
        total = len(filtered_tenders)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        
        # Get page of results
        page_tenders = filtered_tenders[start_idx:end_idx]
        
        return {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit,
            "tenders": page_tenders
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tender/{tender_id}")
async def get_tender(tender_id: str) -> Dict:
    """
    Get detailed information about a specific tender
    
    - **tender_id**: The unique identifier of the tender
    """
    try:
        # Search in both sources
        all_tenders = []
        mygov_tenders = scraper.scrape_mygov_tenders()
        ppip_tenders = scraper.scrape_ppip_tenders()
        all_tenders.extend(mygov_tenders)
        all_tenders.extend(ppip_tenders)
        
        # Find tender by ID
        tender = next(
            (t for t in all_tenders if t.get('reference') == tender_id),
            None
        )
        
        if not tender:
            raise HTTPException(status_code=404, detail="Tender not found")
            
        return tender
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats() -> Dict:
    """Get statistics about available tenders"""
    try:
        # Get all tenders
        all_tenders = []
        mygov_tenders = scraper.scrape_mygov_tenders()
        ppip_tenders = scraper.scrape_ppip_tenders()
        all_tenders.extend(mygov_tenders)
        all_tenders.extend(ppip_tenders)
        
        # Calculate statistics
        total = len(all_tenders)
        open_tenders = len([t for t in all_tenders if t.get('status') == 'open'])
        closing_soon = len([t for t in all_tenders if t.get('status') == 'closing_soon'])
        closed = len([t for t in all_tenders if t.get('status') == 'closed'])
        
        # Get unique entities and categories
        entities = len(set(t.get('procuring_entity') for t in all_tenders if t.get('procuring_entity')))
        categories = len(set(t.get('category') for t in all_tenders if t.get('category')))
        
        return {
            "total_tenders": total,
            "open_tenders": open_tenders,
            "closing_soon": closing_soon,
            "closed_tenders": closed,
            "unique_entities": entities,
            "unique_categories": categories,
            "last_updated": datetime.now(pytz.timezone('Africa/Nairobi')).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/offline-bundle")
async def get_offline_bundle() -> Dict:
    """
    Get a bundle of data for offline access
    Includes recent tenders and basic statistics
    """
    try:
        # Get recent tenders
        all_tenders = []
        mygov_tenders = scraper.scrape_mygov_tenders()
        ppip_tenders = scraper.scrape_ppip_tenders()
        all_tenders.extend(mygov_tenders)
        all_tenders.extend(ppip_tenders)
        
        # Only include non-closed tenders to reduce bundle size
        active_tenders = [
            t for t in all_tenders 
            if t.get('status') in ['open', 'closing_soon']
        ]
        
        # Get basic stats
        stats = await get_stats()
        
        return {
            "tenders": active_tenders,
            "stats": stats,
            "bundle_created": datetime.now(pytz.timezone('Africa/Nairobi')).isoformat(),
            "valid_until": (
                datetime.now(pytz.timezone('Africa/Nairobi')) + 
                timedelta(days=1)
            ).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

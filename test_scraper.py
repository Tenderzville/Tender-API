import logging
from scraper.tender_scraper import TenderScraper
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_scraping():
    scraper = TenderScraper()
    
    # Test MyGov tenders
    logger.info("Testing MyGov tender scraping...")
    mygov_tenders = scraper.scrape_mygov_tenders()
    logger.info(f"Found {len(mygov_tenders)} tenders from MyGov")
    
    # Test PPIP tenders
    logger.info("Testing PPIP tender scraping...")
    ppip_tenders = scraper.scrape_ppip_tenders()
    logger.info(f"Found {len(ppip_tenders)} tenders from PPIP")
    
    # Test PPIP API
    logger.info("Testing PPIP API...")
    api_tenders = scraper.fetch_ppip_api_tenders()
    logger.info(f"Found {len(api_tenders)} tenders from API")
    
    # Save results with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if mygov_tenders:
        scraper.save_to_csv(mygov_tenders, f'data/mygov_tenders_{timestamp}.csv')
    if ppip_tenders:
        scraper.save_to_csv(ppip_tenders, f'data/ppip_tenders_{timestamp}.csv')
    if api_tenders:
        scraper.save_to_csv(api_tenders, f'data/api_tenders_{timestamp}.csv')

if __name__ == "__main__":
    # Create data directory if it doesn't exist
    import os
    os.makedirs("data", exist_ok=True)
    
    test_scraping()

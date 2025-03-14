import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import json
import logging
import time
from typing import List, Dict, Optional
import urllib3
from urllib3.exceptions import InsecureRequestWarning
import re
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Text, Boolean, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import pytz
from dateutil import parser
import textwrap

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Disable InsecureRequestWarning but keep other SSL warnings
urllib3.disable_warnings(InsecureRequestWarning)

# Database setup
Base = declarative_base()

class TenderRecord(Base):
    __tablename__ = 'tenders'
    
    id = Column(Integer, primary_key=True)
    reference = Column(String(100), unique=True)
    title = Column(Text)
    description = Column(Text)
    procuring_entity = Column(String(200))
    procurement_method = Column(String(100))
    category = Column(String(100))
    value = Column(String(100))
    currency = Column(String(10))
    document_url = Column(String(500))
    closing_date = Column(DateTime)
    published_date = Column(DateTime)
    source = Column(String(50))
    is_processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TenderScraper:
    def __init__(self, db_url="sqlite:///tenders.db"):
        # Site configurations
        self.sites = {
            'mygov': {
                'url': 'https://www.mygov.go.ke/all-tenders',
                'table_id': 'datatable',
                'selectors': {
                    'reference': {'class': 'views-field-counter'},
                    'title': {'class': 'views-field-title'},
                    'entity': {'class': 'views-field-field-ten'},
                    'document': {'class': 'views-field-field-tender-documents'},
                    'closing_date': {'class': 'views-field-field-tender-closing-date'}
                }
            },
            'ppip': {
                'base_url': 'https://tenders.go.ke',
                'ocds_url': 'https://tenders.go.ke/api/ocds/tenders',
                'headers': {
                    'Accept': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36'
                }
            }
        }
        
        # Initialize session with retry strategy
        self.session = requests.Session()
        retries = urllib3.util.Retry(
            total=5,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
        self.session.mount('https://', requests.adapters.HTTPAdapter(max_retries=retries))
        
        # Common headers optimized for mobile and Kenyan users
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36',
            'Accept-Language': 'en-KE,sw-KE,en;q=0.9,sw;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }
        
        # Initialize database
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db_session = Session()

    def _make_request(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Optional[requests.Response]:
        """Make HTTP request with mobile optimization and offline support"""
        try:
            # Add mobile-specific query params
            mobile_params = {
                'v': 'mobile',
                'lite': '1'
            }
            if params:
                mobile_params.update(params)
                
            # Use provided headers or default ones
            request_headers = headers if headers else self.headers
                
            response = self.session.get(
                url,
                headers=request_headers,
                params=mobile_params,
                timeout=30,
                verify=False if '.go.ke' in url else True
            )
            
            # Check if we got rate limited
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                logger.warning(f"Rate limited. Waiting {retry_after} seconds")
                time.sleep(retry_after)
                return self._make_request(url, params, headers)
                
            response.raise_for_status()
            return response
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {str(e)}")
            return None

    def _parse_kenyan_date(self, date_str: str) -> Optional[datetime]:
        """Parse date strings in various Kenyan formats"""
        if not date_str or any(x in date_str.lower() for x in ['various', 'multiple', 'closing', 'date', 'www']):
            return None
            
        try:
            # Remove common Kenyan date formatting quirks
            date_str = date_str.replace('hrs', '').replace('HRS', '')
            date_str = date_str.replace('AM', '').replace('PM', '')
            date_str = date_str.replace('A.M.', '').replace('P.M.', '')
            date_str = re.sub(r'(\d)(st|nd|rd|th)', r'\1', date_str)  # Remove ordinal indicators
            date_str = date_str.replace(',', '').strip()
            
            # Try multiple date formats common in Kenya
            formats = [
                '%d %B %Y',           # 15 March 2024
                '%B %d %Y',           # March 15 2024
                '%d/%m/%Y',           # 15/03/2024
                '%Y-%m-%d',           # 2024-03-15
                '%d-%m-%Y',           # 15-03-2024
                '%d.%m.%Y',           # 15.03.2024
                '%d %b %Y',           # 15 Mar 2024
                '%b %d %Y',           # Mar 15 2024
            ]
            
            for fmt in formats:
                try:
                    return pd.to_datetime(date_str, format=fmt)
                except:
                    continue
                    
            # If specific formats fail, try pandas flexible parser
            return pd.to_datetime(date_str)
            
        except Exception as e:
            logger.debug(f"Could not parse date '{date_str}': {str(e)}")
            return None

    def _format_tender_for_mobile(self, tender: Dict) -> Dict:
        """Format tender data for mobile display"""
        try:
            # Convert dates to EAT (UTC+3)
            eat = pytz.timezone('Africa/Nairobi')
            utc = pytz.UTC
            
            # Handle closing date
            if tender.get('closing_date'):
                try:
                    closing_date = parser.parse(tender['closing_date'])
                    if closing_date.tzinfo is None:
                        closing_date = eat.localize(closing_date)
                    tender['closing_date'] = closing_date.astimezone(eat).isoformat()
                except:
                    tender['closing_date'] = None
            
            # Handle published date
            if tender.get('published_date'):
                try:
                    published_date = parser.parse(tender['published_date'])
                    if published_date.tzinfo is None:
                        published_date = eat.localize(published_date)
                    tender['published_date'] = published_date.astimezone(eat).isoformat()
                except:
                    tender['published_date'] = None
            
            # Add mobile-friendly fields
            now = datetime.now(eat)
            
            if tender.get('closing_date'):
                try:
                    closing_date = parser.parse(tender['closing_date'])
                    days_remaining = (closing_date.astimezone(eat) - now).days
                    tender['days_remaining'] = days_remaining
                    tender['status'] = 'closed' if days_remaining < 0 else 'closing_soon' if days_remaining <= 7 else 'open'
                except:
                    tender['days_remaining'] = None
                    tender['status'] = 'unknown'
            
            # Truncate long text for mobile
            if tender.get('title'):
                tender['title'] = textwrap.shorten(tender['title'], width=100, placeholder="...")
            
            if tender.get('description'):
                tender['description'] = textwrap.shorten(tender['description'], width=200, placeholder="...")
            
            # Add metadata for offline access
            tender['last_updated'] = now.isoformat()
            tender['offline_available'] = True
            
            return tender
            
        except Exception as e:
            logger.error(f"Error formatting tender: {str(e)}")
            return tender

    def scrape_mygov_tenders(self) -> List[Dict]:
        """Scrape tenders from mygov.go.ke with mobile optimization"""
        tenders = []
        site_config = self.sites['mygov']
        
        response = self._make_request(site_config['url'])
        if not response:
            return tenders

        soup = BeautifulSoup(response.content, 'html.parser')
        table = soup.find('table', {'id': site_config['table_id']})
        
        if not table:
            logger.warning("Table structure changed on MyGov site")
            return tenders

        for row in table.find('tbody').find_all('tr'):
            try:
                tender = {
                    'reference': row.find('td', site_config['selectors']['reference']).text.strip(),
                    'title': row.find('td', site_config['selectors']['title']).text.strip(),
                    'procuring_entity': row.find('td', site_config['selectors']['entity']).text.strip(),
                    'document_url': None,
                    'closing_date': None
                }
                
                # Handle optional fields
                doc_cell = row.find('td', site_config['selectors']['document'])
                if doc_cell and doc_cell.find('a'):
                    tender['document_url'] = doc_cell.find('a')['href']
                
                date_cell = row.find('td', site_config['selectors']['closing_date'])
                if date_cell:
                    tender['closing_date'] = date_cell.text.strip()
                
                tender['source'] = 'mygov'
                tender['scraped_at'] = datetime.now().isoformat()
                
                # Format for mobile display
                tender = self._format_tender_for_mobile(tender)
                
                tenders.append(tender)
                self._save_to_db(tender)
                
            except Exception as e:
                logger.error(f"Error parsing tender row: {str(e)}")
                continue
        
        logger.info(f"Scraped {len(tenders)} tenders from MyGov")
        return tenders

    def scrape_ppip_tenders(self) -> List[Dict]:
        """Scrape tenders from tenders.go.ke using their OCDS API"""
        tenders = []
        site_config = self.sites['ppip']
        
        try:
            # Get current fiscal year
            current_date = datetime.now()
            if current_date.month >= 7:  # Fiscal year starts in July
                fy = f"{current_date.year}-{current_date.year + 1}"
            else:
                fy = f"{current_date.year - 1}-{current_date.year}"
            
            # Make API request with fiscal year parameter
            headers = {**self.headers, **site_config['headers']}
            params = {'fy': fy}
            
            response = self._make_request(
                site_config['ocds_url'],
                params=params,
                headers=headers
            )
            
            if not response:
                logger.error("Failed to access tenders.go.ke OCDS API")
                return tenders
            
            try:
                data = response.json()
                releases = data.get('releases', [])
                
                for release in releases:
                    try:
                        tender_data = release.get('tender', {})
                        
                        # Extract tender details using OCDS schema
                        tender = {
                            'reference': tender_data.get('id'),
                            'title': tender_data.get('title'),
                            'procuring_entity': release.get('buyer', {}).get('name'),
                            'category': tender_data.get('mainProcurementCategory'),
                            'procurement_method': tender_data.get('procurementMethod'),
                            'value': tender_data.get('value', {}).get('amount'),
                            'currency': tender_data.get('value', {}).get('currency', 'KES'),
                            'closing_date': tender_data.get('tenderPeriod', {}).get('endDate'),
                            'published_date': release.get('date'),
                            'document_url': (
                                tender_data.get('documents', [{}])[0].get('url')
                                if tender_data.get('documents') else None
                            ),
                            'description': tender_data.get('description'),
                            'source': 'ppip',
                            'status': tender_data.get('status')
                        }
                        
                        # Skip invalid tenders
                        if not tender['reference'] or not tender['title']:
                            continue
                        
                        # Format for mobile display
                        tender = self._format_tender_for_mobile(tender)
                        
                        # Save to database
                        self._save_to_db(tender)
                        
                        tenders.append(tender)
                        
                    except Exception as e:
                        logger.error(f"Error processing tender: {str(e)}")
                        continue
                
                logger.info(f"Scraped {len(tenders)} tenders from PPIP OCDS API")
                
            except json.JSONDecodeError:
                logger.error("Invalid JSON response from OCDS API")
            
        except Exception as e:
            logger.error(f"Failed to scrape PPIP: {str(e)}")
            
        return tenders

    def _save_to_db(self, tender: Dict):
        """Save tender to database with improved date handling"""
        try:
            # Convert dates
            closing_date = None
            published_date = None
            
            if 'closing_date' in tender:
                if isinstance(tender['closing_date'], pd.Timestamp):
                    closing_date = tender['closing_date']
                else:
                    closing_date = self._parse_kenyan_date(tender['closing_date'])
                    
            if 'published_date' in tender:
                published_date = self._parse_kenyan_date(tender['published_date'])

            record = TenderRecord(
                reference=tender.get('reference'),
                title=tender.get('title'),
                description=tender.get('description'),
                procuring_entity=tender.get('procuring_entity'),
                procurement_method=tender.get('procurement_method'),
                category=tender.get('category'),
                value=tender.get('value'),
                currency=tender.get('currency', 'KES'),  # Default to KES
                document_url=tender.get('document_url'),
                closing_date=closing_date,
                published_date=published_date,
                source=tender.get('source'),
                is_processed=False
            )
            
            # Check for existing record
            existing = self.db_session.query(TenderRecord).filter_by(
                reference=tender.get('reference'),
                source=tender.get('source')
            ).first()
            
            if not existing:
                self.db_session.add(record)
                self.db_session.commit()
                logger.debug(f"Added new tender: {tender.get('reference')}")
            else:
                # Update if closing date changed
                if closing_date and existing.closing_date != closing_date:
                    existing.closing_date = closing_date
                    existing.updated_at = datetime.utcnow()
                    self.db_session.commit()
                    logger.debug(f"Updated tender {tender.get('reference')} closing date")
                else:
                    logger.debug(f"Tender {tender.get('reference')} already exists")
                
        except Exception as e:
            logger.error(f"Database error: {str(e)}")
            self.db_session.rollback()

    def get_unprocessed_tenders(self) -> List[TenderRecord]:
        """Get tenders that haven't been processed yet"""
        return self.db_session.query(TenderRecord).filter_by(is_processed=False).all()

    def mark_as_processed(self, tender_id: int):
        """Mark a tender as processed"""
        tender = self.db_session.query(TenderRecord).get(tender_id)
        if tender:
            tender.is_processed = True
            tender.updated_at = datetime.utcnow()
            self.db_session.commit()

    def get_mobile_tenders(self, 
                          status: Optional[str] = None,
                          category: Optional[str] = None,
                          entity: Optional[str] = None,
                          days_remaining: Optional[int] = None,
                          offline: bool = False) -> List[Dict]:
        """Get tenders in a mobile-optimized format with filtering
        
        Args:
            status: Filter by status ('open', 'closed', 'closing_soon', 'open_week')
            category: Filter by tender category
            entity: Filter by procuring entity
            days_remaining: Filter by maximum days remaining
            offline: If True, only return tenders marked for offline access
            
        Returns:
            List of tenders formatted for mobile display
        """
        query = self.db_session.query(TenderRecord)
        
        # Apply filters
        if status:
            if status == 'open':
                query = query.filter(TenderRecord.closing_date > datetime.utcnow())
            elif status == 'closed':
                query = query.filter(TenderRecord.closing_date <= datetime.utcnow())
            elif status == 'closing_soon':
                three_days = datetime.utcnow() + pd.Timedelta(days=3)
                query = query.filter(
                    TenderRecord.closing_date > datetime.utcnow(),
                    TenderRecord.closing_date <= three_days
                )
            elif status == 'open_week':
                week = datetime.utcnow() + pd.Timedelta(days=7)
                query = query.filter(
                    TenderRecord.closing_date > datetime.utcnow(),
                    TenderRecord.closing_date <= week
                )
                
        if category:
            query = query.filter(TenderRecord.category.ilike(f'%{category}%'))
            
        if entity:
            query = query.filter(TenderRecord.procuring_entity.ilike(f'%{entity}%'))
            
        if days_remaining is not None:
            deadline = datetime.utcnow() + pd.Timedelta(days=days_remaining)
            query = query.filter(TenderRecord.closing_date <= deadline)
            
        # Get results
        records = query.order_by(TenderRecord.closing_date.asc()).all()
        
        # Format for mobile
        tenders = []
        for record in records:
            tender = {
                'reference': record.reference,
                'title': record.title,
                'procuring_entity': record.procuring_entity,
                'category': record.category,
                'closing_date': record.closing_date,
                'document_url': record.document_url,
                'source': record.source
            }
            
            # Add mobile formatting
            tender = self._format_tender_for_mobile(tender)
            
            # Only include offline-ready tenders if requested
            if offline and not tender.get('offline_available'):
                continue
                
            tenders.append(tender)
            
        return tenders

    def get_tender_stats(self) -> Dict:
        """Get mobile-friendly statistics about available tenders"""
        now = datetime.utcnow()
        stats = {
            'total': self.db_session.query(TenderRecord).count(),
            'open': self.db_session.query(TenderRecord).filter(
                TenderRecord.closing_date > now
            ).count(),
            'closed': self.db_session.query(TenderRecord).filter(
                TenderRecord.closing_date <= now
            ).count(),
            'closing_soon': self.db_session.query(TenderRecord).filter(
                TenderRecord.closing_date > now,
                TenderRecord.closing_date <= now + pd.Timedelta(days=3)
            ).count(),
            'by_source': {},
            'by_category': {},
            'last_updated': pd.Timestamp.now().isoformat()
        }
        
        # Get counts by source
        sources = self.db_session.query(
            TenderRecord.source, 
            func.count(TenderRecord.id)
        ).group_by(TenderRecord.source).all()
        
        stats['by_source'] = {source: count for source, count in sources}
        
        # Get top categories
        categories = self.db_session.query(
            TenderRecord.category, 
            func.count(TenderRecord.id)
        ).filter(
            TenderRecord.category.isnot(None)
        ).group_by(TenderRecord.category).order_by(
            func.count(TenderRecord.id).desc()
        ).limit(5).all()
        
        stats['by_category'] = {cat: count for cat, count in categories}
        
        return stats

    def __del__(self):
        """Clean up database session"""
        self.db_session.close()

    def save_to_csv(self, tenders: List[Dict], filename: str):
        """Save scraped tenders to CSV file"""
        if tenders:
            df = pd.DataFrame(tenders)
            df.to_csv(filename, index=False)
            logger.info(f"Saved {len(tenders)} tenders to {filename}")
        else:
            logger.warning("No tenders to save")

def main():
    scraper = TenderScraper()
    
    # Scrape tenders from both sources
    mygov_tenders = scraper.scrape_mygov_tenders()
    ppip_tenders = scraper.scrape_ppip_tenders()
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scraper.save_to_csv(mygov_tenders, f'mygov_tenders_{timestamp}.csv')
    scraper.save_to_csv(ppip_tenders, f'ppip_tenders_{timestamp}.csv')

if __name__ == "__main__":
    main()

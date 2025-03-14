import telegram
import tweepy
import logging
from typing import Dict, List, Optional
import json
import asyncio
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotificationAgent:
    def __init__(self, config_path: str = 'config.json'):
        self.config = self._load_config(config_path)
        self.telegram_bot = self._setup_telegram()
        self.twitter_api = self._setup_twitter()
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from file or use environment variables"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Return empty config if file doesn't exist
            return {
                'telegram': {'token': '', 'chat_ids': []},
                'twitter': {
                    'consumer_key': '',
                    'consumer_secret': '',
                    'access_token': '',
                    'access_token_secret': ''
                }
            }

    def _setup_telegram(self) -> Optional[telegram.Bot]:
        """Setup Telegram bot"""
        token = self.config['telegram']['token']
        if not token:
            logger.warning("Telegram token not configured")
            return None
        try:
            return telegram.Bot(token=token)
        except Exception as e:
            logger.error(f"Failed to setup Telegram bot: {str(e)}")
            return None

    def _setup_twitter(self) -> Optional[tweepy.API]:
        """Setup Twitter API"""
        twitter_config = self.config['twitter']
        if not all(twitter_config.values()):
            logger.warning("Twitter credentials not configured")
            return None
        try:
            auth = tweepy.OAuthHandler(
                twitter_config['consumer_key'],
                twitter_config['consumer_secret']
            )
            auth.set_access_token(
                twitter_config['access_token'],
                twitter_config['access_token_secret']
            )
            return tweepy.API(auth)
        except Exception as e:
            logger.error(f"Failed to setup Twitter API: {str(e)}")
            return None

    def format_tender_message(self, tender: Dict, platform: str = 'telegram') -> str:
        """Format tender information for different platforms"""
        if platform == 'telegram':
            # Detailed format for Telegram with markdown
            message = (
                f"*New Tender Alert!* 📢\n\n"
                f"*Title:* {tender.get('title', 'N/A')}\n"
                f"*Reference:* `{tender.get('reference', 'N/A')}`\n"
                f"*Entity:* {tender.get('entity', 'N/A')}\n"
                f"*Category:* {tender.get('category', 'N/A')}\n"
                f"*Closing Date:* {tender.get('closing_date', 'N/A')}\n\n"
                f"*Estimated Value:* {tender.get('estimated_value', 'N/A')}\n"
                f"*Risk Level:* {tender.get('risk_level', 'N/A')}\n\n"
                f"View more details on our website: {tender.get('url', '')}"
            )
        else:
            # Shorter format for Twitter due to character limit
            message = (
                f"📢 Tender Alert!\n"
                f"{tender.get('title', 'N/A')[:100]}...\n"
                f"By: {tender.get('entity', 'N/A')}\n"
                f"Closes: {tender.get('closing_date', 'N/A')}\n"
                f"Details: {tender.get('url', '')}"
            )
        return message

    async def send_telegram_message(self, tender: Dict) -> bool:
        """Send tender information to Telegram"""
        if not self.telegram_bot:
            logger.error("Telegram bot not configured")
            return False

        message = self.format_tender_message(tender, 'telegram')
        chat_ids = self.config['telegram']['chat_ids']
        
        success = True
        for chat_id in chat_ids:
            try:
                await self.telegram_bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=telegram.ParseMode.MARKDOWN
                )
                logger.info(f"Sent tender notification to Telegram chat {chat_id}")
            except Exception as e:
                logger.error(f"Failed to send Telegram message to {chat_id}: {str(e)}")
                success = False
        
        return success

    def send_twitter_update(self, tender: Dict) -> bool:
        """Send tender information to Twitter"""
        if not self.twitter_api:
            logger.error("Twitter API not configured")
            return False

        try:
            message = self.format_tender_message(tender, 'twitter')
            self.twitter_api.update_status(status=message)
            logger.info("Sent tender notification to Twitter")
            return True
        except Exception as e:
            logger.error(f"Failed to send Twitter update: {str(e)}")
            return False

    async def notify_all(self, tenders: List[Dict]) -> Dict[str, int]:
        """Send notifications for multiple tenders to all platforms"""
        stats = {
            'telegram_sent': 0,
            'twitter_sent': 0,
            'failed': 0
        }

        for tender in tenders:
            telegram_success = await self.send_telegram_message(tender)
            twitter_success = self.send_twitter_update(tender)
            
            if telegram_success:
                stats['telegram_sent'] += 1
            if twitter_success:
                stats['twitter_sent'] += 1
            if not (telegram_success or twitter_success):
                stats['failed'] += 1

            # Add delay between notifications to avoid rate limits
            await asyncio.sleep(1)

        return stats

    def save_notification_log(self, tender: Dict, platforms: List[str], success: bool):
        """Log notification details for tracking"""
        log_entry = {
            'tender_id': tender.get('id'),
            'timestamp': datetime.now().isoformat(),
            'platforms': platforms,
            'success': success
        }
        
        try:
            with open('notification_log.json', 'a') as f:
                json.dump(log_entry, f)
                f.write('\n')
        except Exception as e:
            logger.error(f"Failed to save notification log: {str(e)}")

async def main():
    # Example usage
    notifier = NotificationAgent()
    
    # Example tender data
    test_tender = {
        'id': '12345',
        'title': 'Supply of Medical Equipment',
        'reference': 'TEN/2024/001',
        'entity': 'Ministry of Health',
        'category': 'Medical Supplies',
        'closing_date': '2024-04-01',
        'estimated_value': 'KES 5,000,000',
        'risk_level': 'low',
        'url': 'https://tenders.go.ke/tender/12345'
    }
    
    # Send notifications
    stats = await notifier.notify_all([test_tender])
    logger.info(f"Notification statistics: {stats}")

if __name__ == "__main__":
    asyncio.run(main())

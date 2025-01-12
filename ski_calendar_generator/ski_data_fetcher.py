import asyncio
import json
import logging
import os
from pathlib import Path
import requests
from typing import List, Optional

logger = logging.getLogger(__name__)

class SkiDataFetcher:
    BASE_URL = os.environ.get("SKI_DATA_API_URL", "https://ski-data-api.homelab.davidemarcoli.dev/api/v1")
    CACHE_DIR = Path("cache")
    
    def __init__(self):
        self.CACHE_DIR.mkdir(exist_ok=True)
        self.competitions_cache_file = self.CACHE_DIR / "competitions.json"
        self.details_cache_file = self.CACHE_DIR / "competition_details.json"
    
    async def fetch_competitions(self) -> List[dict]:
        """Fetch list of all competitions, using cache if available."""
        logger.info("Fetching competitions list")
        if self.competitions_cache_file.exists():
            with open(self.competitions_cache_file, 'r') as f:
                return json.load(f)
        
        response = requests.get(f"{self.BASE_URL}/competitions")
        competitions = response.json()
        
        # Cache the results
        with open(self.competitions_cache_file, 'w') as f:
            json.dump(competitions, f, indent=2)
        
        return competitions
    
    async def fetch_competition_details(self, event_id: str, force_refresh: bool = False) -> Optional[dict]:
        """Fetch details for a specific competition."""
        # First check if we have it in our cached details
        if self.details_cache_file.exists() and not force_refresh:
            with open(self.details_cache_file, 'r') as f:
                details_cache = json.load(f)
                if event_id in details_cache:
                    return details_cache[event_id]
        else:
            details_cache = {}
        
        logger.info(f"Fetching details for event {event_id}")
        response = requests.get(f"{self.BASE_URL}/competitions/{event_id}")
        if response.status_code == 200:
            details = response.json()
            
            # Update cache
            details_cache[event_id] = details
            with open(self.details_cache_file, 'w') as f:
                json.dump(details_cache, f, indent=2)
            
            return details
        return None
    
    async def fetch_all_details(self, force_refresh: bool = False):
        """Fetch details for all competitions with rate limiting."""
        logger.info("Starting full data refresh")
        competitions = await self.fetch_competitions()
        
        if self.details_cache_file.exists() and not force_refresh:
            logger.info("Using cached details")
            return
        
        details_cache = {}
        for comp in competitions:
            event_id = comp['event_id']
            
            details = await self.fetch_competition_details(event_id, force_refresh)
            if details:
                details_cache[event_id] = details
            
            # Rate limiting
            await asyncio.sleep(10)
        
        # Save all details to cache
        with open(self.details_cache_file, 'w') as f:
            json.dump(details_cache, f, indent=2)
        
        logger.info("Data refresh completed")

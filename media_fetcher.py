import asyncio
import aiohttp
import aiofiles
import os
from typing import List, Dict, Any, Optional
from tenacity import retry, wait_exponential, stop_after_attempt

from config import settings
from logger import logger

class MediaFetcher:
    def __init__(self):
        self.api_key = settings.PEXELS_API_KEY.get_secret_value()
        self.base_url = "https://api.pexels.com/videos/search"
        self.semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_FETCHES)
        self.logger = logger.bind(component="MediaFetcher")

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": self.api_key
        }

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        before_sleep=lambda retry_state: logger.warning(
            "Retrying Pexels fetch",
            attempt=retry_state.attempt_number,
            error=str(retry_state.outcome.exception())
        )
    )
    async def fetch_query(self, session: aiohttp.ClientSession, query: str) -> Optional[Dict[str, Any]]:
        async with self.semaphore:
            self.logger.info("Fetching media for query", query=query)
            params = {
                "query": query,
                "per_page": 1,
                "orientation": "portrait" # For shorts/reels
            }
            
            async with session.get(
                self.base_url,
                headers=self._get_headers(),
                params=params,
                timeout=aiohttp.ClientTimeout(total=settings.MEDIA_TIMEOUT_SECONDS)
            ) as response:
                if response.status == 429:
                    self.logger.warning("Rate limited by Pexels API", query=query)
                    response.raise_for_status()

                if response.status != 200:
                    self.logger.error("Pexels API error", status=response.status, query=query)
                    return None

                data = await response.json()
                videos = data.get("videos", [])
                
                if not videos:
                    self.logger.info("No videos found for query", query=query)
                    return None
                    
                video_data = videos[0]
                self.logger.info("Successfully fetched video", query=query, video_id=video_data.get("id"))
                return {
                    "query": query,
                    "id": video_data.get("id"),
                    "url": video_data.get("url"),
                    "files": video_data.get("video_files", [])
                }

    async def fetch_all_queries(self, queries: List[str]) -> List[Dict[str, Any]]:
        self.logger.info("Starting concurrent media fetch", num_queries=len(queries))
        
        # Use custom TCPConnector for connection pooling
        connector = aiohttp.TCPConnector(limit=settings.MAX_CONCURRENT_FETCHES)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [self.fetch_query(session, q) for q in queries]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            valid_results = []
            for r in results:
                if isinstance(r, Exception):
                    self.logger.error("Fetch task failed with exception", error=str(r))
                elif r is not None:
                    valid_results.append(r)
                    
            self.logger.info("Finished media fetch", successful_fetches=len(valid_results))
            return valid_results

    async def download_video(self, session: aiohttp.ClientSession, url: str, output_path: str) -> Optional[str]:
        self.logger.info("Downloading video file", url=url, output_path=output_path)
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=600)) as response:
                response.raise_for_status()
                async with aiofiles.open(output_path, mode='wb') as f:
                    while True:
                        chunk = await response.content.read(1024 * 1024) # 1MB chunks
                        if not chunk:
                            break
                        await f.write(chunk)
            self.logger.info("Successfully downloaded video", path=output_path)
            return output_path
        except Exception as e:
            self.logger.error("Failed to download video", error=str(e), url=url)
            return None

fetcher = MediaFetcher()

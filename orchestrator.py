import asyncio
import signal
import uuid
import os
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from config import settings
from logger import logger
from ai_engine import engine as ai_engine
from media_fetcher import fetcher as media_fetcher
from video_renderer import renderer as video_renderer
from publisher import publisher
from db import init_db, AsyncSessionLocal, Topic, ContentItem, TopicStatus, ContentItemStatus

class Orchestrator:
    def __init__(self):
        self.logger = logger.bind(component="Orchestrator")
        self.scheduler = AsyncIOScheduler()
        self.is_running = False

    def _select_best_video_file(self, files: list) -> str:
        """
        Intelligently selects the best video file from the Pexels files array.
        Targets 9:16 portrait aspect ratio (e.g. 1080x1920) at the highest available
        resolution. Falls back to closest aspect-ratio match if no exact portrait found.
        """
        TARGET_RATIO = 9 / 16  # portrait

        best: dict | None = None
        best_score = float('inf')

        for f in files:
            w = f.get('width', 0)
            h = f.get('height', 0)
            if not w or not h:
                continue
            ratio = w / h
            score = abs(ratio - TARGET_RATIO)
            # Prefer higher resolution among equally-scored candidates
            if score < best_score or (
                score == best_score and w * h > (best.get('width', 0) * best.get('height', 0))
            ):
                best_score = score
                best = f

        if best is None:
            raise ValueError("No valid video files found in Pexels asset")

        self.logger.info(
            "Selected best video file",
            width=best.get('width'), height=best.get('height'),
            link=best.get('link', '')[:60]
        )
        return best['link']

    async def _ensure_topic(self, session) -> Topic:
        """Ensures there is at least one PENDING or PROCESSING topic."""
        query = select(Topic).where(Topic.status.in_([TopicStatus.PENDING, TopicStatus.PROCESSING]))
        result = await session.execute(query)
        topic = result.scalars().first()

        if not topic:
            self.logger.info("No pending topics. Generating a new one.")
            topic_prompt = await ai_engine.generate_dynamic_topic()
            topic = Topic(prompt=topic_prompt, status=TopicStatus.PENDING)
            session.add(topic)
            await session.commit()
            await session.refresh(topic)
            
        return topic

    async def _ensure_content_item(self, session, topic: Topic) -> ContentItem:
        query = select(ContentItem).where(ContentItem.topic_id == topic.id)
        result = await session.execute(query)
        item = result.scalars().first()
        
        if not item:
            item = ContentItem(topic_id=topic.id, status=ContentItemStatus.PENDING)
            session.add(item)
            topic.status = TopicStatus.PROCESSING
            await session.commit()
            await session.refresh(item)
            
        return item

    async def run_pipeline(self):
        """
        The state-aware core pipeline execution logic.
        """
        if getattr(self, '_pipeline_running', False):
            self.logger.warning("Pipeline is already running, skipping this interval.")
            return
            
        self._pipeline_running = True
        run_id = str(uuid.uuid4())
        pipeline_logger = self.logger.bind(run_id=run_id)
        pipeline_logger.info("Starting pipeline execution cycle")

        try:
            async with AsyncSessionLocal() as session:
                topic = await self._ensure_topic(session)
                item = await self._ensure_content_item(session, topic)
                
                # Phase 1: Generation (Narrative & Audio)
                if item.status == ContentItemStatus.PENDING:
                    pipeline_logger.info("Phase 1: Generation", topic_id=topic.id)
                    narrative = await ai_engine.generate_narrative(topic.prompt)
                    item.narrative_json = narrative.model_dump()
                    
                    audio_filename = f"audio_{item.id}.mp3"
                    audio_path = os.path.join(settings.ASSETS_DIR, "raw", audio_filename)
                    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
                    
                    await ai_engine.generate_voiceover(narrative.voiceover_script, audio_path)
                    item.audio_path = audio_path
                    item.status = ContentItemStatus.AUDIO_GENERATED
                    await session.commit()
                    pipeline_logger.info("Phase 1 Complete")

                # Phase 2: Media Retrieval
                if item.status == ContentItemStatus.AUDIO_GENERATED:
                    pipeline_logger.info("Phase 2: Media Fetching", item_id=item.id)
                    queries = item.narrative_json.get('search_queries_for_pexels', [])
                    
                    # Ensure we have at least some queries
                    if not queries:
                         raise ValueError("No search queries generated by AI.")

                    # Fetch metadata
                    media_assets = await media_fetcher.fetch_all_queries(queries)
                    
                    # Download actual videos
                    async with aiohttp.ClientSession() as http_session:
                        downloaded_paths = []
                        for idx, asset in enumerate(media_assets):
                            # Intelligently pick the best-quality portrait file
                            video_url = self._select_best_video_file(asset['files'])
                            filename = f"video_{item.id}_{idx}.mp4"
                            filepath = os.path.join(settings.ASSETS_DIR, "raw", filename)
                            path = await media_fetcher.download_video(http_session, video_url, filepath)
                            if path:
                                downloaded_paths.append(path)
                    
                    if not downloaded_paths:
                        raise Exception("Failed to download any video assets")

                    # SQLAlchemy does NOT track in-place mutations on JSON columns.
                    # We must reassign the whole object to trigger dirty-tracking.
                    updated_json = dict(item.narrative_json)
                    updated_json['downloaded_videos'] = downloaded_paths
                    item.narrative_json = updated_json
                    item.status = ContentItemStatus.MEDIA_FETCHED
                    await session.commit()
                    pipeline_logger.info("Phase 2 Complete", downloaded_count=len(downloaded_paths))

                # Phase 3: Video Rendering
                if item.status == ContentItemStatus.MEDIA_FETCHED:
                    pipeline_logger.info("Phase 3: Video Rendering", item_id=item.id)
                    video_paths = item.narrative_json.get('downloaded_videos', [])
                    output_path = os.path.join(settings.ASSETS_DIR, "rendered", f"final_{item.id}.mp4")
                    
                    await video_renderer.render_video(video_paths, item.audio_path, output_path)
                    
                    item.rendered_video_path = output_path
                    item.status = ContentItemStatus.RENDERED
                    await session.commit()
                    pipeline_logger.info("Phase 3 Complete")

                # Phase 4: Publishing
                if item.status == ContentItemStatus.RENDERED:
                    pipeline_logger.info("Phase 4: Publishing", item_id=item.id)
                    caption = f"{item.narrative_json.get('social_caption', '')}\n\n{' '.join(item.narrative_json.get('hashtags', []))}"
                    
                    post_id = await publisher.publish_reel(item.rendered_video_path, caption)
                    
                    if post_id:
                        item.status = ContentItemStatus.PUBLISHED
                        topic.status = TopicStatus.PUBLISHED
                        await session.commit()
                        pipeline_logger.info("Phase 4 Complete. Pipeline cycle finished successfully.")
                    else:
                        pipeline_logger.error("Publishing failed, will retry next cycle.")

        except Exception as e:
            pipeline_logger.error("Pipeline execution failed", error=str(e), exc_info=True)
            # In a real system, you might mark the item/topic as FAILED here
            # But leaving it in current state allows retry on next run
        finally:
            self._pipeline_running = False

    async def start(self):
        """
        Initialises the scheduler. Awaits DB init before starting any work
        to prevent a race condition where the pipeline queries tables that
        don't exist yet.
        """
        self.logger.info("Initializing Orchestrator daemon")
        self.is_running = True

        # ── CRITICAL: fully initialise the database FIRST ──────────────────
        await init_db()
        # ───────────────────────────────────────────────────────────────────

        interval = settings.SCHEDULE_INTERVAL_SECONDS
        self.scheduler.add_job(
            self.run_pipeline,
            'interval',
            seconds=interval,
            next_run_time=None
        )
        self.scheduler.start()

        self.logger.info("Orchestrator daemon started", interval_seconds=interval)

        # First run immediately, guaranteed that the DB is ready
        await self.run_pipeline()

    async def shutdown(self, sig):
        """
        Gracefully shuts down the orchestrator.
        """
        self.logger.info(f"Received exit signal {sig.name}...")
        self.is_running = False
        self.scheduler.shutdown(wait=False)
        self.logger.info("Orchestrator shutdown complete.")
        
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        
        asyncio.get_event_loop().stop()

def main():
    orchestrator = Orchestrator()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # loop.add_signal_handler() is NOT supported on Windows.
    # signal.signal() works cross-platform (Win32 + Unix).
    def _shutdown_handler(signum, frame):
        sig = signal.Signals(signum)
        loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(orchestrator.shutdown(sig), loop=loop)
        )

    signal.signal(signal.SIGINT, _shutdown_handler)
    # SIGTERM is only available on Unix; guard for Windows
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown_handler)

    try:
        # start() is now async — run it until complete before handing off to run_forever
        loop.run_until_complete(orchestrator.start())
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Event loop closed.")

if __name__ == "__main__":
    main()

import asyncio
import os
from pathlib import Path
from typing import Optional

from config import settings
from logger import logger

# Session file persists login cookies across container restarts.
# Mount this path as a Docker volume to survive container redeploys.
SESSION_FILE = Path("data/ig_session.json")


class Publisher:
    def __init__(self):
        self.username = settings.INSTAGRAM_USERNAME
        self.password = settings.INSTAGRAM_PASSWORD.get_secret_value() if settings.INSTAGRAM_PASSWORD else ""
        self.proxy = settings.INSTAGRAM_PROXY.get_secret_value() if settings.INSTAGRAM_PROXY else ""
        self.logger = logger.bind(component="Publisher")
        self._client = None  # lazy-initialised on first publish

        if self.username and not self.proxy:
            self.logger.warning(
                "INSTAGRAM_PROXY is not set. Cloud-hosted deployments WILL get IP-banned by Instagram. "
                "Set INSTAGRAM_PROXY to a residential proxy URL (http://user:pass@host:port)."
            )

    def _build_client(self):
        """
        Constructs an instagrapi Client pre-configured with:
          - Residential proxy routing (if INSTAGRAM_PROXY is set)
          - Human-like request pacing via delay_range
        """
        from instagrapi import Client

        cl = Client()
        cl.delay_range = [2, 5]  # Mimics human request cadence

        if self.proxy:
            cl.set_proxy(self.proxy)
            self.logger.info("Proxy configured for Instagram client", proxy_host=self.proxy.split("@")[-1])
        else:
            self.logger.warning("No proxy set — running without residential IP routing.")

        return cl

    def _get_client(self):
        """
        Returns a logged-in instagrapi Client. Strategy:
          1. Load cached session file → attempt a reuse login (avoids fresh-login bot signals).
          2. If the session is stale/expired, perform a fresh login and save the new session.

        The session file MUST be on a persistent volume in Docker so it survives container restarts.
        A fresh login every hour is one of the most reliable bot-detection triggers on Instagram.
        """
        from instagrapi.exceptions import LoginRequired, BadPassword, ChallengeRequired

        cl = self._build_client()

        if SESSION_FILE.exists():
            try:
                cl.load_settings(SESSION_FILE)
                # Reuse login: sends a lightweight auth ping, not a full login request.
                cl.login(self.username, self.password)
                self.logger.info("Restored Instagram session from cached file")
                return cl
            except (LoginRequired, Exception) as e:
                self.logger.warning(
                    "Cached session is invalid or expired — performing fresh login",
                    error=str(e)
                )
                SESSION_FILE.unlink(missing_ok=True)
                cl = self._build_client()  # Fresh client, clear any stale state

        # Fresh login path
        try:
            cl.login(self.username, self.password)
        except BadPassword:
            self.logger.error("Instagram login failed: incorrect password. Check INSTAGRAM_PASSWORD in .env.")
            raise
        except ChallengeRequired:
            self.logger.error(
                "Instagram challenge (2FA / suspicious login) triggered. "
                "This usually means your proxy IP is not residential, or the account needs 2FA approval. "
                "Log in manually via the Instagram app on the same network/device first."
            )
            raise

        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        cl.dump_settings(SESSION_FILE)
        self.logger.info("Fresh Instagram login successful — session saved to disk")
        return cl

    async def publish_reel(self, video_path: str, caption: str) -> Optional[str]:
        """
        Uploads a rendered MP4 as an Instagram Reel.
        - Returns the post ID string on success.
        - Returns None on failure (orchestrator will retry on the next cycle).
        - Falls back to simulation mode if credentials are not set.
        """
        self.logger.info(
            "Starting publishing process",
            video_path=video_path,
            caption_preview=caption[:80]
        )

        # ── Simulation mode ──────────────────────────────────────────────────
        if not self.username or not self.password:
            self.logger.warning(
                "Instagram credentials not configured (INSTAGRAM_USERNAME / INSTAGRAM_PASSWORD). "
                "Running in SIMULATION mode — no post will be uploaded."
            )
            await asyncio.sleep(1)
            self.logger.info("Simulated publish complete.")
            return "simulated_post_id"

        # ── Real upload via instagrapi ───────────────────────────────────────
        try:
            loop = asyncio.get_running_loop()

            def _upload():
                cl = self._client or self._get_client()
                self._client = cl  # Cache for subsequent runs within the same process
                media = cl.clip_upload(
                    path=video_path,
                    caption=caption,
                )
                # Persist any session cookie updates after a successful upload
                cl.dump_settings(SESSION_FILE)
                return str(media.pk)

            post_id = await loop.run_in_executor(None, _upload)
            self.logger.info("Reel published successfully", post_id=post_id)
            return post_id

        except Exception as e:
            self.logger.error("Failed to publish Reel", error=str(e), exc_info=True)
            # Invalidate the cached client — next cycle will force a fresh session check
            self._client = None
            return None


publisher = Publisher()

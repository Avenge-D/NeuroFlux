import asyncio
import os
import ffmpeg
from pathlib import Path
from typing import List

from logger import logger

# Each raw Pexels clip is trimmed to this duration before concatenation.
# Fast cuts = higher retention on Shorts/Reels.
CLIP_DURATION_SECONDS = 4

class VideoRenderer:
    def __init__(self):
        self.logger = logger.bind(component="VideoRenderer")
        self.target_width = 1080
        self.target_height = 1920

    async def render_video(self, video_paths: List[str], audio_path: str, output_path: str) -> str:
        self.logger.info(
            "Starting video render",
            num_clips=len(video_paths),
            clip_duration_s=CLIP_DURATION_SECONDS,
            output=output_path
        )
        try:
            # ffmpeg.run() is blocking — offload to a thread so the event loop stays free
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._render_sync, video_paths, audio_path, output_path)
            self.logger.info("Successfully rendered video", path=output_path)
            return output_path
        except Exception as e:
            self.logger.error("Failed to render video", error=str(e), exc_info=True)
            raise

    def _render_sync(self, video_paths: List[str], audio_path: str, output_path: str):
        processed_streams = []

        for path in video_paths:
            # Convert Windows backslashes — FFmpeg requires forward slashes
            node = ffmpeg.input(str(Path(path).as_posix()), ss=0, t=CLIP_DURATION_SECONDS)

            v = (
                node.video
                # Scale by width first so width is always >= 1080
                .filter('scale', w=self.target_width, h=-2)
                # Then scale by height if still too short
                .filter('scale', w=-2, h='if(lt(ih,{h}),{h},ih)'.format(h=self.target_height))
                # Centre-crop to exact 9:16 portrait frame
                .filter('crop', w=self.target_width, h=self.target_height)
                # Normalise frame rate
                .filter('fps', fps=30, round='up')
                # Ensure consistent SAR for concat
                .filter('setsar', r='1/1')
            )
            processed_streams.append(v)

        # Concatenate all trimmed+normalised clips into one video stream (no audio)
        joined_video = ffmpeg.concat(*processed_streams, v=1, a=0)

        # Overlay the TTS audio track; `shortest=1` stops the video when audio ends
        audio_node = ffmpeg.input(str(Path(audio_path).as_posix())).audio

        out_posix = str(Path(output_path).as_posix())
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        (
            ffmpeg
            .output(
                joined_video,
                audio_node,
                out_posix,
                format='mp4',            # explicit container — never guess from path
                vcodec='libx264',
                preset='fast',
                crf=23,
                pix_fmt='yuv420p',
                acodec='aac',
                audio_bitrate='192k',
                shortest=1,
                loglevel='error'
            )
            .run(overwrite_output=True)
        )

renderer = VideoRenderer()

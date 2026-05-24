import asyncio
import json
from typing import List

from pydantic import BaseModel, Field
from groq import AsyncGroq
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
import edge_tts

from config import settings
from logger import logger


# ── Output Schema ────────────────────────────────────────────────────────────
class MediaNarrative(BaseModel):
    theme: str = Field(..., description="The core theme of the narrative")
    voiceover_script: str = Field(..., description="The spoken voiceover script")
    search_queries_for_pexels: List[str] = Field(..., description="List of highly specific search queries for Pexels")
    social_caption: str = Field(..., description="The caption for social media including engagement hooks")
    hashtags: List[str] = Field(..., description="A list of relevant hashtags")


class AIEngine:
    def __init__(self):
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY.get_secret_value())
        self.model_name = settings.GROQ_MODEL
        self.logger = logger.bind(component="AIEngine")

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(Exception),
        before_sleep=lambda retry_state: logger.warning(
            "Retrying AI generation due to error",
            attempt=retry_state.attempt_number,
            error=str(retry_state.outcome.exception())
        )
    )
    async def generate_narrative(self, topic_prompt: str) -> MediaNarrative:
        self.logger.info("Starting AI narrative generation", topic=topic_prompt)

        system_instruction = (
            "You are an elite creative director and AI media strategist. "
            "Your job is to generate highly engaging, viral-optimized narratives for social media. "
            "You must respond ONLY with valid JSON conforming to this exact schema:\n"
            '{"theme": string, "voiceover_script": string, '
            '"search_queries_for_pexels": [string, ...], '
            '"social_caption": string, "hashtags": [string, ...]}\n'
            "Do not include markdown code blocks or any text outside the JSON. "
            "Ensure search_queries_for_pexels are highly visual, literal, and suitable for stock video search."
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": f"Create a viral social media narrative about: {topic_prompt}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=1024,
            )

            raw_json = response.choices[0].message.content
            narrative = MediaNarrative.model_validate_json(raw_json)

            self.logger.info("Successfully generated narrative", theme=narrative.theme)
            return narrative

        except Exception as e:
            self.logger.error("Failed to generate narrative", error=str(e))
            raise

    async def generate_dynamic_topic(self, context: str = "wealth, hustle, and futuristic technology") -> str:
        self.logger.info("Generating dynamic topic", context=context)
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Give me ONE highly engaging, specific, and viral 1-sentence topic "
                            f"for a short-form video about {context}. "
                            f"Just the topic sentence, no quotes, no extra text."
                        )
                    }
                ],
                temperature=0.9,
                max_tokens=80,
            )
            topic = response.choices[0].message.content.strip().strip('"')
            self.logger.info("Generated dynamic topic", topic=topic)
            return topic
        except Exception as e:
            self.logger.error("Failed to generate dynamic topic", error=str(e))
            return "Mind-blowing facts about artificial intelligence shaping our future."

    async def generate_voiceover(self, script: str, output_path: str) -> str:
        self.logger.info("Generating TTS voiceover", script_length=len(script))
        try:
            voice = "en-US-ChristopherNeural"
            communicate = edge_tts.Communicate(script, voice)
            await communicate.save(output_path)
            self.logger.info("TTS voiceover generated", path=output_path)
            return output_path
        except Exception as e:
            self.logger.error("Failed to generate TTS", error=str(e))
            raise


engine = AIEngine()

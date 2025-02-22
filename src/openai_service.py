import os
from openai import OpenAI
import logging

logger = logging.getLogger("gamebot")

class OpenAIService:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def generate_game_description(self, game_name, game_info=""):
        try:
            logger.info(f"Generating AI description for: {game_name}")
            prompt = f"Describe the game '{game_name}' in an engaging way. Include notable features and what makes it special."
            if game_info:
                prompt += f"\nAdditional info: {game_info}"

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a knowledgeable gaming expert."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message["content"]
        except Exception as e:
            logger.error(f"OpenAI API Error: {str(e)}")
            return f"Sorry, I couldn't generate a description due to an error: {str(e)}"

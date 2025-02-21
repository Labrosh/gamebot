# **GameBot AI Description Generation Plan**

## **🔹 Overview**
To ensure accurate game descriptions, AI should be used **strategically** to avoid hallucinated (fake) information.  
This plan ensures AI:
1. **Refines existing Steam descriptions** (when available).  
2. **Generates a new description if Steam has none**, but fact-checks itself.  
3. **Falls back to a genre-based summary** if it doesn’t confidently know the game.

---

## **🔹 AI Description Generation Logic**
### **1️⃣ If Steam has a description → AI improves it**
Instead of asking AI to "make up" a description, we give it **the Steam description** and ask it to improve clarity & engagement.

```python
import openai

def generate_ai_description(self, game_name: str, steam_description: str) -> Optional[str]:
    """Generate an AI-powered description, refining the Steam-provided one."""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a game journalist who writes engaging descriptions."},
                {"role": "user", "content": f"Improve this description of {game_name}: {steam_description}"}
            ],
            max_tokens=150
        )
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"AI description generation failed: {e}")
        return None
✅ Pros: Keeps AI grounded in real data.
✅ Cons: If Steam’s description is bad, AI might still need improvement.

2️⃣ If Steam has no description → AI generates one, but fact-checks itself
To prevent hallucinated information, we ask AI to verify its own response.

python
Copy
Edit
import openai

def generate_ai_description(self, game_name: str) -> Optional[str]:
    """Generate an AI-powered description while checking for accuracy."""

    try:
        # Step 1: Generate a description
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a game expert."},
                {"role": "user", "content": f"Tell me about the game {game_name}. If you are unsure about anything, say 'I don't know' rather than making something up."}
            ],
            max_tokens=150
        )
        description = response["choices"][0]["message"]["content"]

        # Step 2: Ask AI to verify its own accuracy
        verification = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are verifying a game description for accuracy."},
                {"role": "user", "content": f"Is this description accurate? {description} If not, say 'I don't know'."}
            ],
            max_tokens=50
        )

        verified_response = verification["choices"][0]["message"]["content"]
        if "I don't know" in verified_response:
            return None  # Reject AI response if it's uncertain

        return description
    except Exception as e:
        logger.error(f"AI description generation failed: {e}")
        return None
✅ Pros: AI self-checks its responses, reducing fake details.
✅ Cons: Takes two AI calls instead of one (slightly slower).

3️⃣ If AI still doesn’t know → Provide a genre-based fallback
If AI doesn’t know the game, it provides a general genre summary instead so users still get something useful.

python
Copy
Edit
import openai

def generate_ai_description(self, game_name: str, genre: str) -> Optional[str]:
    """Generate an AI-powered description, falling back to a genre overview if needed."""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a game expert."},
                {"role": "user", "content": f"Tell me about the game {game_name}. If you don’t know it, instead provide a general description of {genre} games."}
            ],
            max_tokens=150
        )
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"AI description generation failed: {e}")
        return None
✅ Pros: Ensures users always get a response, even for obscure games.
✅ Cons: Might not be as specific as a real game description.

🔹 Implementation Plan
Integrate these AI description functions into commands.py.
Modify !info to use AI only when needed.
Test responses for popular games & niche games.
Fine-tune AI prompts if needed.
If AI hallucinations still happen, tweak self-verification logic.
🔹 Final Thoughts
This hybrid approach balances accuracy, speed, and usefulness.
AI never replaces Steam data unless necessary.
Users always get a description, but AI doesn’t guess wildly.
📌 Next Steps
Once I have my API keys:

Replace the generate_ai_description() function with real OpenAI API calls.
Test different games and ensure AI isn’t making things up.
Optimize prompts if necessary.

## **🔹 Simplified Approach (Updated Feb 21, 2025)**

After review, a simpler implementation might work better:

```python
def generate_ai_description(self, game_name: str) -> Optional[str]:
    """Simple AI fallback for when Steam has no description."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You're a helpful gaming bot. Be honest if you don't know a game."},
                {"role": "user", "content": f"What's the game '{game_name}' about? Keep it brief (2-3 sentences) and say 'I don't know this game' if unsure."}
            ],
            max_tokens=150
        )
        description = response.choices[0].message.content
        
        # Simple check for uncertainty
        if any(phrase in description.lower() for phrase in [
            "i don't know", 
            "i'm not sure", 
            "i'm unfamiliar"
        ]):
            return None
            
        return description
    except Exception as e:
        logger.error(f"AI description failed for {game_name}: {e}")
        return None
```

### Why Simpler is Better
- Only used as fallback when Steam has no description
- Single API call instead of multiple verification steps
- Clear "I don't know" response for unknown games
- Low stakes - it's okay if we occasionally miss a game description
- Works with existing error handling in commands.py

---
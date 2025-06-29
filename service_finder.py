import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
import aiohttp
import re
import random

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class ServiceFinder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cache = {}

    async def chatgpt_score_and_expertise(self, business_name, reviews, user_query):
        cache_key = (business_name.lower(), user_query.lower())
        if cache_key in self.cache:
            return self.cache[cache_key]

        prompt = (
            f"The user is searching for: {user_query}.\n"
            "You will be provided reviews and info for one business.\n"
            "Your task:\n"
            "- Provide ONE AI Score (0-10) at the top.\n"
            "- Then write a concise explanation of how well this business fits the need.\n"
            "- Provide Expertise section:\n"
            "  * Best quality: ...\n"
            "  * Time in business: Estimate from review dates, ratings age, clues.\n"
            "  * Average price: $ estimate or range ($, $$, $$$, or $100-200). Never say 'not specified'.\n"
            "⚠ Keep output under 900 characters. No duplicate scores unless justified.\n\n"
            f"Business: {business_name}\n"
            "Reviews:\n"
            + "\n".join(f"- {r}" for r in reviews[:5])
        )

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                text = data["choices"][0]["message"]["content"].strip()

                score_match = re.search(r'(\d+)/10', text)
                score = int(score_match.group(1)) if score_match else random.randint(6, 9)

                explanation = re.sub(r'AI Score.*', '', text).strip()

                if len(explanation) > 900:
                    explanation = explanation[:880] + "...\n(response trimmed)"

                result = {
                    "score": score,
                    "full_text": f"**AI Score: {score}/10**\n\n{explanation}"
                }

                self.cache[cache_key] = result
                return result

    async def query_google_places(self, term, location):
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {"query": f"{term} in {location}", "key": GOOGLE_API_KEY}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                return await resp.json()

    async def get_place_details(self, place_id):
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            "place_id": place_id,
            "fields": "name,rating,formatted_address,formatted_phone_number,review,user_ratings_total,url",
            "key": GOOGLE_API_KEY
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                return await resp.json()

    @commands.command()
    async def findservice(self, ctx, *, query):
        location = "Miami"
        g_results = await self.query_google_places(query, location)
        if "results" not in g_results:
            await ctx.send("❗ No results found.")
            return

        seen_names = set()
        unique_results = []
        for place in g_results["results"]:
            name = place.get("name", "").strip()
            if name.lower() not in seen_names:
                unique_results.append(place)
                seen_names.add(name.lower())
            if len(unique_results) == 5:
                break

        if not unique_results:
            await ctx.send("❗ No unique businesses found.")
            return

        businesses = []
        scores_seen = set()

        for place in unique_results:
            details = await self.get_place_details(place["place_id"])
            result = details.get("result", {})
            name = result.get("name", "Unknown")
            rating = result.get("rating", "N/A")
            address = result.get("formatted_address", "N/A")
            phone = result.get("formatted_phone_number", "N/A")
            reviews = [r["text"] for r in result.get("reviews", []) if "text" in r]
            url = f"https://www.google.com/maps/place/?q=place_id:{place['place_id']}"

            gpt = await self.chatgpt_score_and_expertise(name, reviews, query)

            while gpt["score"] in scores_seen:
                gpt["score"] = min(10, max(0, gpt["score"] + random.choice([-1, 1])))
            scores_seen.add(gpt["score"])

            businesses.append({
                "name": name,
                "rating": rating,
                "address": address,
                "phone": phone,
                "url": url,
                "score": gpt["score"],
                "full_text": gpt["full_text"]
            })

        # Sort by score descending
        businesses.sort(key=lambda x: x["score"], reverse=True)

        for idx, biz in enumerate(businesses, 1):
            if biz["score"] >= 8:
                embed_color = 0x00ff00  # Green
            elif biz["score"] >= 5:
                embed_color = 0x808080  # Gray
            else:
                embed_color = 0xff0000  # Red

            embed = discord.Embed(
                title=f"Option #{idx}: {biz['name']} - ⭐ {biz['rating']}/5",
                color=embed_color
            )
            embed.add_field(
                name="Details",
                value=(
                    f"📍 {biz['address']}\n"
                    f"📞 {biz['phone']}\n"
                    f"🔗 [View on Google]({biz['url']})"
                ),
                inline=False
            )
            embed.add_field(
                name="AI Analysis",
                value=biz["full_text"],
                inline=False
            )

            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ServiceFinder(bot))

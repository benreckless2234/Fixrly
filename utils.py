import discord
from discord.ext import commands

class Utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def embedtest(self, ctx):
        embed = discord.Embed(title="Sample Embed", description="This is a test embed!", color=0x3498db)
        embed.add_field(name="Field 1", value="Some value", inline=True)
        embed.add_field(name="Field 2", value="Another value", inline=True)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Utils(bot))

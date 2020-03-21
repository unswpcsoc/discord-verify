from discord.ext import commands

class Verify(commands.Cog):
    @commands.command(name="verify")
    async def verify(self, ctx):
        print("test")

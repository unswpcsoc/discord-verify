import discord

from config import BOT_TOKEN

client = discord.Client()

@client.event
async def on_message(message):
    pass

@client.event
async def on_reaction_add(reaction, user):
    pass

client.run(BOT_TOKEN)

import discord
from redbot.core import commands
from redbot.core.bot import Red

class TeamLFG(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='lfg')
    async def lfg(self, ctx, message: str, game: str, number_of_people: int):
        user = ctx.author

        if not user.voice or not user.voice.channel:
            await ctx.send(f"{user.mention}, you must be connected to a voice channel to use this command.")
            return

        if number_of_people < 1 or number_of_people > 10:
            await ctx.send(f"{user.mention}, please enter a number of people between 1 and 10.")
            return

        voice_channel = user.voice.channel

        # Try to update the user limit of the voice channel
        try:
            await voice_channel.edit(user_limit=number_of_people)
        except discord.Forbidden:
            await ctx.send("I do not have permission to edit this voice channel.")
            return
        except Exception as e:
            await ctx.send(f"Something went wrong while editing the voice channel: {e}")
            return

        # Create an invite link
        try:
            invite = await voice_channel.create_invite(max_age=3600, max_uses=0, unique=True, reason="LFG Command")
        except Exception as e:
            await ctx.send(f"Failed to create an invite link: {e}")
            return

        # Send the message
        embed = discord.Embed(
            title=f"Looking For Group - {game}",
            description=message,
            color=discord.Color.blue()
        )
        embed.add_field(name="Voice Channel", value=voice_channel.name, inline=True)
        embed.add_field(name="Players Needed", value=str(number_of_people), inline=True)
        embed.add_field(name="Join Here", value=invite.url, inline=False)
        embed.set_footer(text=f"Created by {user.display_name}", icon_url=user.avatar.url if user.avatar else None)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(TeamLFG(bot))

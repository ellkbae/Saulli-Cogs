import discord
from discord.ext import commands
import json
import os
import aiohttp
import imghdr
import asyncio
from typing import Optional, List

class TeamManagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.teams_file = 'teams_data.json'
        self.config_file = 'team_battle_config.json'
        self.events_channel_id = None
        self.active_battles = {}
        self.battle_winner_roles = []
        self.load_teams()
        self.load_config()

    def load_teams(self):
        """Load teams data from JSON file"""
        if os.path.exists(self.teams_file):
            try:
                with open(self.teams_file, 'r') as f:
                    self.teams = json.load(f)
            except json.JSONDecodeError:
                self.teams = {}
                self.save_teams()
        else:
            self.teams = {}
            self.save_teams()

    def save_teams(self):
        """Save teams data to JSON file"""
        with open(self.teams_file, 'w') as f:
            json.dump(self.teams, f, indent=4)

    def load_config(self):
        """Load battle configuration"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.battle_winner_roles = config.get('battle_winner_roles', [])
            except json.JSONDecodeError:
                self.battle_winner_roles = []
                self.save_config()
        else:
            self.battle_winner_roles = []
            self.save_config()

    def save_config(self):
        """Save battle configuration"""
        with open(self.config_file, 'w') as f:
            json.dump({
                'battle_winner_roles': self.battle_winner_roles
            }, f, indent=4)

    async def validate_image_url(self, url: str) -> bool:
        """
        Validate if the provided URL is a valid image
        Returns True if it's a valid image, False otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return False
                    
                    # Read a small portion of the image to validate
                    content = await response.read()
                    
                    # Use imghdr to detect image type
                    image_type = imghdr.what(None, h=content)
                    
                    # Check if it's a valid image type
                    return image_type in ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp']
        except Exception:
            return False

    def can_select_winner(self, user):
        """Check if user can select a battle winner"""
        # Administrators always can select
        if user.guild_permissions.administrator:
            return True
        
        # Check if user has any of the allowed roles
        return any(role.id in self.battle_winner_roles for role in user.roles)

    @commands.command(name='addbattlerole')
    @commands.has_permissions(administrator=True)
    async def add_battle_role(self, ctx, role: discord.Role):
        """Add a role that can select battle winners"""
        if role.id not in self.battle_winner_roles:
            self.battle_winner_roles.append(role.id)
            self.save_config()
            await ctx.send(f"Role {role.name} can now select battle winners.")
        else:
            await ctx.send(f"Role {role.name} is already allowed to select battle winners.")

    @commands.command(name='removebattlerole')
    @commands.has_permissions(administrator=True)
    async def remove_battle_role(self, ctx, role: discord.Role):
        """Remove a role's ability to select battle winners"""
        if role.id in self.battle_winner_roles:
            self.battle_winner_roles.remove(role.id)
            self.save_config()
            await ctx.send(f"Role {role.name} can no longer select battle winners.")
        else:
            await ctx.send(f"Role {role.name} was not in the list of roles that can select battle winners.")

    @commands.command(name='listbattleroles')
    @commands.has_permissions(administrator=True)
    async def list_battle_roles(self, ctx):
        """List roles that can select battle winners"""
        if not self.battle_winner_roles:
            await ctx.send("No roles are currently allowed to select battle winners.")
            return

        # Resolve role names
        role_names = []
        for role_id in self.battle_winner_roles:
            role = ctx.guild.get_role(role_id)
            if role:
                role_names.append(role.name)
            else:
                # Remove invalid role IDs
                self.battle_winner_roles.remove(role_id)
                self.save_config()

        embed = discord.Embed(
            title="Roles Allowed to Select Battle Winners", 
            description="\n".join(role_names), 
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @commands.group(name='team')
    @commands.check(lambda ctx: ctx.author.guild_permissions.administrator)
    async def team_management(self, ctx):
        """Base command for team management"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Invalid team command. Use !team create/add/remove/list/info/setlogo")

    @team_management.command(name='create')
    async def create_team(self, ctx, team_name: str, logo_url: Optional[str] = None, *, description: str = "No description provided"):
        """Create a new team with optional logo"""
        if team_name in self.teams:
            await ctx.send(f"Team '{team_name}' already exists!")
            return

        # Validate logo URL if provided
        logo_valid = False
        if logo_url:
            logo_valid = await self.validate_image_url(logo_url)
            if not logo_valid:
                await ctx.send("Invalid logo URL. The team will be created without a logo.")

        # Create team with optional logo
        self.teams[team_name] = {
            "description": description,
            "members": [],
            "wins": 0,
            "losses": 0,
            "match_log": [],
            "logo_url": logo_url if logo_valid else None
        }
        self.save_teams()
        
        # Confirm team creation
        embed = discord.Embed(title="Team Created", color=discord.Color.green())
        embed.add_field(name="Team Name", value=team_name, inline=False)
        embed.add_field(name="Description", value=description, inline=False)
        if logo_valid:
            embed.set_thumbnail(url=logo_url)
        
        await ctx.send(embed=embed)

    @team_management.command(name='delete')
    async def delete_team(self, ctx, team_name: str):
        """Delete a team from the list and remove it from the JSON file"""
        if team_name not in self.teams:
            await ctx.send(f"Team '{team_name}' does not exist!")
            return

        del self.teams[team_name]  # Remove from dictionary
        self.save_teams()  # Save updated data to JSON

        await ctx.send(f"Team '{team_name}' has been deleted successfully!")

    @team_management.command(name='setlogo')
    async def set_team_logo(self, ctx, team_name: str, logo_url: str):
        """Set or update a team's logo"""
        if team_name not in self.teams:
            await ctx.send(f"Team '{team_name}' does not exist!")
            return

        # Validate logo URL
        logo_valid = await self.validate_image_url(logo_url)
        if not logo_valid:
            await ctx.send("Invalid logo URL. Please provide a valid image URL.")
            return

        # Update team logo
        self.teams[team_name]['logo_url'] = logo_url
        self.save_teams()

        # Confirm logo update
        embed = discord.Embed(title="Team Logo Updated", color=discord.Color.blue())
        embed.add_field(name="Team Name", value=team_name, inline=False)
        embed.set_thumbnail(url=logo_url)
        
        await ctx.send(embed=embed)

    @team_management.command(name='add')
    async def add_member(self, ctx, team_name: str, member: discord.Member):
        """Add a member to a team by mentioning them"""
        if team_name not in self.teams:
            await ctx.send(f"Team '{team_name}' does not exist!")
            return

        if member.id in self.teams[team_name]["members"]:
            await ctx.send(f"{member.mention} is already in the team!")
            return

        self.teams[team_name]["members"].append(member.id)
        self.save_teams()
        await ctx.send(f"{member.mention} added to team '{team_name}'!")

    @team_management.command(name='remove')
    async def remove_member(self, ctx, team_name: str, user_id: int):
        """Remove a member from a team"""
        if team_name not in self.teams:
            await ctx.send(f"Team '{team_name}' does not exist!")
            return

        if user_id not in self.teams[team_name]["members"]:
            await ctx.send(f"User {user_id} is not in the team!")
            return

        self.teams[team_name]["members"].remove(user_id)
        self.save_teams()
        await ctx.send(f"User {user_id} removed from team '{team_name}'!")

    @team_management.command(name='list')
    async def list_teams(self, ctx):
        """List all existing teams"""
        if not self.teams:
            await ctx.send("No teams have been created yet!")
            return

        embed = discord.Embed(title="Team List", color=discord.Color.blue())
        for team_name, team_data in self.teams.items():
            embed.add_field(
                name=team_name, 
                value=f"Members: {len(team_data['members'])}\n"
                      f"Wins: {team_data['wins']}\n"
                      f"Losses: {team_data['losses']}", 
                inline=False
            )
        await ctx.send(embed=embed)

    @team_management.command(name='info')
    async def team_info(self, ctx, team_name: str):
        """Get detailed information about a specific team"""
        if team_name not in self.teams:
            await ctx.send(f"Team '{team_name}' does not exist!")
            return

        team = self.teams[team_name]
        embed = discord.Embed(title=f"Team: {team_name}", color=discord.Color.green())
        embed.description = team['description']
        
        # Fetch usernames dynamically
        member_mentions = []
        for member_id in team['members']:
            member = ctx.guild.get_member(member_id)
            member_mentions.append(member.mention if member else f"Unknown User ({member_id})")
        
        embed.add_field(name="Members", value="\n".join(member_mentions) or "No members", inline=False)
        embed.add_field(name="Wins", value=team['wins'], inline=True)
        embed.add_field(name="Losses", value=team['losses'], inline=True)
        
        # Add team logo if available
        if team.get('logo_url'):
            embed.set_thumbnail(url=team['logo_url'])
        
        await ctx.send(embed=embed)

    @commands.command(name='battle')
    async def team_battle(self, ctx, team1: str, team2: str, *, game_name: str = "Unspecified Game"):
        """Create a team battle with manual winner selection"""
        # Validate teams exist
        if team1 not in self.teams or team2 not in self.teams:
            await ctx.send("One or both teams do not exist!")
            return

        # Check if user has permission to create battles
        if not self.can_select_winner(ctx.author):
            await ctx.send("You do not have permission to create team battles.")
            return

        # Create battle embed with team logos
        embed = discord.Embed(
            title="Team Battle Setup", 
            description=f"Game: {game_name}", 
            color=discord.Color.blue()
        )
        
        # Add team information
        team1_info = self.teams[team1]
        team2_info = self.teams[team2]
        
        # Add team names and stats
        embed.add_field(name=f"{team1}", value=f"Wins: {team1_info['wins']}\nLosses: {team1_info['losses']}", inline=True)
        embed.add_field(name=f"{team2}", value=f"Wins: {team2_info['wins']}\nLosses: {team2_info['losses']}", inline=True)
        
        # Add team logos if available
        if team1_info.get('logo_url'):
            embed.set_image(url=team1_info['logo_url'])
        
        # Add team reactions for winner selection
        battle_message = await ctx.send(embed=embed)
        
        team1_emoji = "1️⃣"
        team2_emoji = "2️⃣"
        await battle_message.add_reaction(team1_emoji)
        await battle_message.add_reaction(team2_emoji)

        # Store battle information
        self.active_battles[battle_message.id] = {
            "team1": team1,
            "team2": team2,
            "game_name": game_name,
            "battle_date": str(ctx.message.created_at)
        }

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle winner selection via reactions"""
        # Check if the reaction is on an active battle
        battle_info = self.active_battles.get(reaction.message.id)
        if not battle_info:
            return

        # Ensure only authorized users can select the winner
        if not self.can_select_winner(user) or user.bot:
            await reaction.remove(user)
            return

        # Determine winner based on reaction
        if reaction.emoji == "1️⃣":
            winner = battle_info['team1']
            loser = battle_info['team2']
        elif reaction.emoji == "2️⃣":
            winner = battle_info['team2']
            loser = battle_info['team1']
        else:
            return

        # Update team stats
        self.teams[winner]['wins'] += 1
        self.teams[loser]['losses'] += 1

        # Create detailed match log entry
        match_result = {
            "teams": [battle_info['team1'], battle_info['team2']],
            "winner": winner,
            "loser": loser,
            "game_name": battle_info['game_name'],
            "battle_date": battle_info['battle_date']
        }

        # Add log to both teams
        self.teams[battle_info['team1']]['match_log'].append(match_result)
        self.teams[battle_info['team2']]['match_log'].append(match_result)
        self.save_teams()

        # Create result embed
        result_embed = discord.Embed(
            title="Team Battle Result", 
            description=f"🏆 {winner} has defeated {loser} in {battle_info['game_name']}!", 
            color=discord.Color.gold()
        )
        result_embed.add_field(name="Winner", value=winner, inline=True)
        result_embed.add_field(name="Loser", value=loser, inline=True)
        result_embed.add_field(name="Game", value=battle_info['game_name'], inline=False)
        result_embed.set_footer(text=f"Battle winner selected by {user.name}")

        # Send to the same channel
        await reaction.message.channel.send(embed=result_embed)

        # Remove the active battle
        del self.active_battles[reaction.message.id]

    @commands.command(name='matchlog')
    async def view_match_log(self, ctx, team_name: str):
        """View a team's match history"""
        if team_name not in self.teams:
            await ctx.send(f"Team '{team_name}' does not exist!")
            return

        match_log = self.teams[team_name]['match_log']
        
        if not match_log:
            await ctx.send(f"No match history for {team_name}.")
            return

        # Create paginated embed for match log
        embeds = []
        for i in range(0, len(match_log), 5):
            embed = discord.Embed(
                title=f"{team_name} - Match History", 
                color=discord.Color.blue()
            )
            
            for match in match_log[i:i+5]:
                result_text = f"{team_name} {'defeated' if match['winner'] == team_name else 'lost to'} "
                result_text += f"{match['team2'] if match['winner'] == match['team1'] else match['team1']} "
                result_text += f"in {match['game_name']} on {match['battle_date']}"
                embed.add_field(name=f"Match {i + embeds.index(embed) + 1}", value=result_text, inline=False)
            
            embeds.append(embed)

        # Send first page
        current_page = 0
        message = await ctx.send(embed=embeds[current_page])

        # Add navigation reactions if multiple pages
        if len(embeds) > 1:
            await message.add_reaction("⬅️")
            await message.add_reaction("➡️")

            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ["⬅️", "➡️"] and reaction.message.id == message.id

            while True:
                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

                    if str(reaction.emoji) == "➡️" and current_page < len(embeds) - 1:
                        current_page += 1
                        await message.edit(embed=embeds[current_page])
                        await message.remove_reaction(reaction, user)

                    elif str(reaction.emoji) == "⬅️" and current_page > 0:
                        current_page -= 1
                        await message.edit(embed=embeds[current_page])
                        await message.remove_reaction(reaction, user)

                except asyncio.TimeoutError:
                    await message.clear_reactions()
                    break

def setup(bot):
    bot.add_cog(TeamManagementCog(bot))

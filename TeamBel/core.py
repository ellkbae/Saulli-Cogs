import discord
from redbot.core import commands
from redbot.core.bot import Red
import uuid
import json
import os
import aiohttp
import imghdr
import asyncio
from typing import Optional, List

class TeamBel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.teams_file = 'teams_data.json'
        self.config_file = 'team_battle_config.json'
        self.events_channel_id = None
        self.active_battles = {}
        self.battle_winner_roles = []
        self.battle_config = {}
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
                    self.events_channel_id = config.get('events_channel_id')
                    
                    # Load battle image URL if exists
                    self.battle_config = {
                        'battle_image_url': config.get('battle_image_url')
                    }
            except json.JSONDecodeError:
                self.reset_config()
        else:
            self.reset_config()

    def reset_config(self):
        """Reset configuration to default values"""
        self.battle_winner_roles = []
        self.events_channel_id = None
        self.battle_config = {}
        self.save_config()

    def save_config(self):
        """Save battle configuration"""
        with open(self.config_file, 'w') as f:
            json.dump({
                'battle_winner_roles': self.battle_winner_roles,
                'events_channel_id': self.events_channel_id,
                'battle_image_url': self.battle_config.get('battle_image_url')
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

    @commands.command(name='seteventschannel')
    @commands.has_permissions(administrator=True)
    async def set_events_channel(self, ctx, channel: discord.TextChannel = None):
        """Set the channel for battle event announcements"""
        # If no channel is specified, use the current channel
        channel = channel or ctx.channel
        
        self.events_channel_id = channel.id
        self.save_config()
        
        embed = discord.Embed(
            title="Events Channel Set", 
            description=f"Battle announcements will now be sent to {channel.mention}", 
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

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
            await ctx.send("Invalid team command. Use *team create/add/remove/list/info/setlogo")

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
        """List teams with pagination"""
        # Convert teams to a sorted list
        sorted_teams = sorted(self.teams.keys())
        
        if not sorted_teams:
            await ctx.send("No teams have been created yet.")
            return

        # Initialize pagination
        self.team_list_pages = {}
        self.team_list_current_page = {}

        # Create initial page
        def create_team_list_embed(start_index):
            embed = discord.Embed(
                title="Team List", 
                color=discord.Color.blue()
            )
            
            # Add up to 2 teams per page
            for i in range(start_index, min(start_index + 2, len(sorted_teams))):
                team_name = sorted_teams[i]
                team_info = self.teams[team_name]
                
                embed.add_field(
                    name=team_name, 
                    value=(
                        f"**Description:** {team_info['description']}\n"
                        f"**Wins:** {team_info['wins']}\n"
                        f"**Losses:** {team_info['losses']}\n"
                        f"**Members:** {len(team_info['members'])}"
                    ), 
                    inline=False
                )
            
            # Add page info
            current_page = start_index // 2 + 1
            total_pages = (len(sorted_teams) + 1) // 2
            embed.set_footer(text=f"Page {current_page}/{total_pages}")
            
            return embed, current_page, total_pages

        # Send initial page
        initial_embed, current_page, total_pages = create_team_list_embed(0)
        message = await ctx.send(embed=initial_embed)

        # Store page information for this message
        self.team_list_pages[message.id] = {
            'teams': sorted_teams,
            'current_page': current_page,
            'total_pages': total_pages,
            'create_embed': create_team_list_embed
        }
        self.team_list_current_page[message.id] = 0

        # Add navigation reactions
        if total_pages > 1:
            await message.add_reaction('➡️')
            await message.add_reaction('⬅️')

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle team list pagination"""
        # Check if this is a team list message
        if user.bot or reaction.message.id not in self.team_list_pages:
            return

        # Check if user is trying to paginate
        if reaction.emoji == '➡️':
            # Get page information
            page_info = self.team_list_pages[reaction.message.id]
            current_index = self.team_list_current_page[reaction.message.id]
            
            # Calculate next page index
            next_index = current_index + 2
            
            # Check if we've reached the end
            if next_index >= len(page_info['teams']):
                await reaction.remove(user)
                return

            # Create new embed
            new_embed, new_page, total_pages = page_info['create_embed'](next_index)
            
            # Update message
            await reaction.message.edit(embed=new_embed)
            
            # Update tracking
            self.team_list_current_page[reaction.message.id] = next_index
            
            # Add previous page reaction if not first page
            if next_index > 0:
                await reaction.message.add_reaction('⬅️')
            
            # Remove used reaction
            await reaction.remove(user)
        
        elif reaction.emoji == '⬅️':
            # Get page information
            page_info = self.team_list_pages[reaction.message.id]
            current_index = self.team_list_current_page[reaction.message.id]
            
            # Calculate previous page index
            prev_index = max(0, current_index - 2)
            
            # Create new embed
            new_embed, new_page, total_pages = page_info['create_embed'](prev_index)
            
            # Update message
            await reaction.message.edit(embed=new_embed)
            
            # Update tracking
            self.team_list_current_page[reaction.message.id] = prev_index
            
            # Remove used reaction
            await reaction.remove(user)

    @team_management.command(name='resetmatchlog')
    async def reset_match_log(self, ctx, team_name: str):
        """Reset a team's match log"""
        # Check if team exists
        if team_name not in self.teams:
            await ctx.send(f"Team '{team_name}' not found!")
            return

        # Confirm with the user before resetting
        confirm_message = await ctx.send(
            embed=discord.Embed(
                title="Reset Match Log Confirmation", 
                description=f"Are you sure you want to reset the match log for {team_name}? \n\n"
                            "React with ✅ to confirm or ❌ to cancel.",
                color=discord.Color.orange()
            )
        )

        # Add confirmation reactions
        await confirm_message.add_reaction('✅')
        await confirm_message.add_reaction('❌')

        def check(reaction, user):
            return (
                user == ctx.author and 
                str(reaction.emoji) in ['✅', '❌'] and 
                reaction.message.id == confirm_message.id
            )

        try:
            # Wait for user's confirmation reaction
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

            if str(reaction.emoji) == '✅':
                # Reset match log
                self.teams[team_name]['match_log'] = []
                self.save_teams()

                # Create confirmation embed
                embed = discord.Embed(
                    title="Match Log Reset", 
                    description=f"Match log for team '{team_name}' has been cleared.", 
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
            else:
                # Cancelled
                await ctx.send("Match log reset cancelled.")

        except asyncio.TimeoutError:
            # Timeout if no reaction within 60 seconds
            await ctx.send("Confirmation timed out. Match log was not reset.")

    @team_management.command(name='updatedesc')
    async def update_team_description(self, ctx, team_name: str, *, new_description: str):
        """Update an existing team's description"""
        if team_name not in self.teams:
            await ctx.send(f"Team '{team_name}' not found!")
            return

        # Update description
        self.teams[team_name]['description'] = new_description
        self.save_teams()

        # Create confirmation embed
        embed = discord.Embed(
            title="Team Description Updated", 
            color=discord.Color.green()
        )
        embed.add_field(name="Team", value=team_name, inline=False)
        embed.add_field(name="New Description", value=new_description, inline=False)
        
        await ctx.send(embed=embed)

    @team_management.command(name='rename')
    async def rename_team(self, ctx, old_name: str, new_name: str):
        """Rename an existing team"""
        # Check if old team exists
        if old_name not in self.teams:
            await ctx.send(f"Team '{old_name}' not found!")
            return

        # Check if new name is already taken
        if new_name in self.teams:
            await ctx.send(f"Team name '{new_name}' is already in use!")
            return

        # Rename the team
        # Create a copy of the team data with the new key
        self.teams[new_name] = self.teams.pop(old_name)

        # Save the updated teams
        self.save_teams()

        # Create confirmation embed
        embed = discord.Embed(
            title="Team Renamed", 
            color=discord.Color.green()
        )
        embed.add_field(name="Old Name", value=old_name, inline=False)
        embed.add_field(name="New Name", value=new_name, inline=False)
        
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

    @commands.group(name='battle')
    async def battle_management(self, ctx):
        """Base command for battle management"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Invalid battle command. Use !battle create or !battle setimage")

    @battle_management.command(name='setimage')
    @commands.has_permissions(administrator=True)
    async def set_battle_image(self, ctx, image_url: str):
        """Set a custom battle image for future battles"""
        # Validate the image URL
        is_valid = await self.validate_image_url(image_url)
        if not is_valid:
            await ctx.send("Invalid image URL. Please provide a valid image link.")
            return

        # Update battle config
        self.battle_config['battle_image_url'] = image_url
        self.save_config()

        # Create confirmation embed
        embed = discord.Embed(title="Battle Image Updated", color=discord.Color.green())
        embed.set_image(url=image_url)
        embed.description = "This image will be used in future team battles."
        
        await ctx.send(embed=embed)

    @battle_management.command(name='create')
    async def team_battle(self, ctx, team1: str, team2: str, *, game_name: str = "Unspecified Game"):
        """Create a team battle with team details and members"""
        # Validate teams exist
        if team1 not in self.teams or team2 not in self.teams:
            await ctx.send("One or both teams do not exist!")
            return

        # Check if user has permission to create battles
        if not self.can_select_winner(ctx.author):
            await ctx.send("You do not have permission to create team battles.")
            return

        # Create battle embed with team details
        embed = discord.Embed(
            title="Team Battle Announcement", 
            description=f"🎮 **{game_name}**", 
            color=discord.Color.blue()
        )
        
        # Fetch team information
        team1_info = self.teams[team1]
        team2_info = self.teams[team2]
        
        # Fetch team members' mentions
        async def get_team_members(team_members):
            mentions = []
            for member_id in team_members:
                member = ctx.guild.get_member(member_id)
                if member:
                    mentions.append(member.mention)
            return mentions or ["No members"]

        team1_members = await get_team_members(team1_info['members'])
        team2_members = await get_team_members(team2_info['members'])

        # Add team details to embed
        embed.add_field(
            name=f"🔵 {team1}", 
            value=f"**Wins:** {team1_info['wins']}\n"
                  f"**Losses:** {team1_info['losses']}\n"
                  f"**Members:** {', '.join(team1_members[:5])}" + 
                  (f"\n*+ {len(team1_members) - 5} more*" if len(team1_members) > 5 else ""), 
            inline=True
        )
        
        embed.add_field(
            name=f"🔴 {team2}", 
            value=f"**Wins:** {team2_info['wins']}\n"
                  f"**Losses:** {team2_info['losses']}\n"
                  f"**Members:** {', '.join(team2_members[:5])}" + 
                  (f"\n*+ {len(team2_members) - 5} more*" if len(team2_members) > 5 else ""), 
            inline=True
        )

        # Add thumbnail logos if available
        embed.set_thumbnail(url="https://res.cloudinary.com/dltcsc9i3/image/upload/c_thumb,w_200,g_face/v1743107009/tvt-logo-01_cqvugz.png")
        
        # Add custom battle image if set
        if self.battle_config.get('battle_image_url'):
            battle_image = self.battle_config['battle_image_url']
            is_valid = await self.validate_image_url(battle_image)
            if is_valid:
                embed.set_image(url=battle_image)

        # Determine where to send the battle announcement
        if self.events_channel_id:
            # Try to send to the configured events channel
            try:
                events_channel = ctx.guild.get_channel(self.events_channel_id)
                if events_channel:
                    battle_message = await events_channel.send(embed=embed)
                else:
                    # Fallback to current channel if events channel is no longer valid
                    battle_message = await ctx.send(embed=embed)
                    await ctx.send("⚠️ Configured events channel not found. Sent to current channel.")
            except discord.Forbidden:
                # Fallback if bot lacks permissions in events channel
                battle_message = await ctx.send(embed=embed)
                await ctx.send("⚠️ Cannot send to events channel. Check bot permissions.")
        else:
            # Send to current channel if no events channel set
            battle_message = await ctx.send(embed=embed)
        
        # Add selection reactions
        team1_emoji = "1️⃣"
        team2_emoji = "2️⃣"
        await battle_message.add_reaction(team1_emoji)
        await battle_message.add_reaction(team2_emoji)

        # Store battle information
        self.active_battles[battle_message.id] = {
            "team1": team1,
            "team2": team2,
            "game_name": game_name,
            "battle_date": ctx.message.created_at.strftime("%B %d, %Y")
        }

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle team list pagination and other reactions"""
        # Ignore bot reactions and messages not in our tracked list
        if user.bot:
            return

        # Check for team list pagination first
        if hasattr(self, 'team_list_pages') and reaction.message.id in self.team_list_pages:
            # Team list pagination logic
            page_info = self.team_list_pages[reaction.message.id]
            
            try:
                current_index = self.team_list_current_page[reaction.message.id]
                
                if reaction.emoji == '➡️':
                    # Move to next page
                    next_index = current_index + 2
                    if next_index < len(page_info['teams']):
                        new_embed, new_page, total_pages = page_info['create_embed'](next_index)
                        await reaction.message.edit(embed=new_embed)
                        self.team_list_current_page[reaction.message.id] = next_index
                
                elif reaction.emoji == '⬅️':
                    # Move to previous page
                    prev_index = max(0, current_index - 2)
                    new_embed, new_page, total_pages = page_info['create_embed'](prev_index)
                    await reaction.message.edit(embed=new_embed)
                    self.team_list_current_page[reaction.message.id] = prev_index
                
                # Remove the user's reaction
                await reaction.remove(user)
            
            except Exception as e:
                print(f"Error in team list pagination: {e}")
                return

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

        # Create detailed match log entry with unique ID
        match_result = {
            "match_id": str(uuid.uuid4()),  # Generate a unique ID for the match
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

    @team_management.command(name='matchlog')
    async def view_match_log(self, ctx, team_name: str):
        """View the match history for a specific team"""
        if team_name not in self.teams:
            await ctx.send(f"Team '{team_name}' not found!")
            return

        match_log = self.teams[team_name]['match_log']
        
        if not match_log:
            await ctx.send(f"No match history for {team_name}.")
            return

        # Create an embed for match history
        embed = discord.Embed(
            title=f"Match History for {team_name}", 
            color=discord.Color.blue()
        )

        result_text = ""
        for match in match_log:
            # Use get() to safely access keys, with fallbacks
            teams = match.get('teams', [])
            winner = match.get('winner', 'Unknown')
            loser = match.get('loser', 'Unknown')
            game_name = match.get('game_name', 'Unspecified Game')
            battle_date = match.get('battle_date', 'Unknown Date')
            match_id = match.get('match_id', 'N/A')

            # Determine the opposing team
            opposing_team = teams[0] if teams and teams[0] != team_name else (teams[1] if len(teams) > 1 else 'Unknown')
            
            # Format the match log entry
            result_text += f"**Match ID:** `{match_id}`\n\n"
            result_text += f"{team_name} vs {opposing_team}\n "
            result_text += f"**{game_name}** on {battle_date}, "
            result_text += f"Result: {'🏆 Won' if winner == team_name else '💀 Lost'}\n"

        embed.description = result_text
        
        await ctx.send(embed=embed)

    @team_management.command(name='deletematch')
    async def delete_match(self, ctx, match_id: str):
        """Delete a specific match from all involved teams' match logs"""
        # Find and remove the match from all team logs
        deleted_match = False
        for team_name, team_data in self.teams.items():
            # Find and remove the match with the given ID
            team_data['match_log'] = [
                match for match in team_data['match_log'] 
                if match.get('match_id') != match_id
            ]

        # Determine if any matches were deleted
        for team_name, team_data in self.teams.items():
            if not deleted_match:
                # Check if the match was in this team's log
                if not any(match.get('match_id') == match_id for match in team_data['match_log']):
                    deleted_match = True

        # Save changes
        self.save_teams()

        # Create result embed
        if deleted_match:
            embed = discord.Embed(
                title="Match Deleted", 
                description=f"Match with ID `{match_id}` has been removed from all team logs.", 
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="Match Not Found", 
                description=f"No match found with ID `{match_id}`.", 
                color=discord.Color.red()
            )
        
        await ctx.send(embed=embed)

    @team_management.command(name='matchinfo')
    async def view_match_details(self, ctx, match_id: str):
        """View details of a specific match by its ID"""
        matching_matches = []

        # Search for the match across all teams
        for team_name, team_data in self.teams.items():
            for match in team_data['match_log']:
                if match.get('match_id') == match_id:
                    matching_matches.append((team_name, match))

        # Create embed to show match details
        if matching_matches:
            match = matching_matches[0][1]  # Take the first match found
            embed = discord.Embed(
                title="Match Details", 
                color=discord.Color.blue()
            )
            embed.add_field(name="Match ID", value=match_id, inline=False)
            embed.add_field(name="Teams", value=" vs ".join(match['teams']), inline=False)
            embed.add_field(name="Winner", value=match['winner'], inline=True)
            embed.add_field(name="Loser", value=match['loser'], inline=True)
            embed.add_field(name="Game", value=match['game_name'], inline=False)
            embed.add_field(name="Date", value=match['battle_date'], inline=False)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send(
                embed=discord.Embed(
                    title="Match Not Found", 
                    description=f"No match found with ID `{match_id}`.", 
                    color=discord.Color.red()
                )
            )

def setup(bot):
    bot.add_cog(TeamBel(bot))

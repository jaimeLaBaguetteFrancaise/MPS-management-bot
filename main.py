import discord
from discord import app_commands
from discord.ext import commands
import os
from dotenv import load_dotenv
from pymongo import MongoClient
import datetime


load_dotenv()
TOKEN = os.getenv("token")
MONGO_URI = os.getenv("MONGO_URI")  # Your full MongoDB Atlas connection string in .env

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Connect to MongoDB YOU MIGHT WANNA USE ANOTHER DB IF YOU PLAN TO FORK THIS PROJECT
mongo_client = MongoClient(MONGO_URI)
db = mongo_client['mpsbotdb']  
guild_settings_col = db['guild_settings'] 
matches_col = db['matches'] 


async def get_guild_settings(guild_id: int):
    """Fetch guild settings from DB or create default."""
    guild_data = guild_settings_col.find_one({"guild_id": str(guild_id)})
    if guild_data is None:
        
        default_doc = {
            "guild_id": str(guild_id),
            "ateam_role_id": None,
            "bteam_role_id": None,
            "ff_role_id": None
        }
        guild_settings_col.insert_one(default_doc)
        return default_doc
    return guild_data


async def update_guild_setting(guild_id: int, key: str, value):
    """Update one setting field for a guild."""
    guild_settings_col.update_one(
        {"guild_id": str(guild_id)},
        {"$set": {key: value}},
        upsert=True
    )


@bot.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {bot.user}, ALL CREDITS GOES TO ADOUAM8383")


@tree.command(name="dmall", description="Send a DM to every user in the team server")
@app_commands.describe(message="The message to send via DM")
async def dmall(interaction: discord.Interaction, message: str):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    if guild is None:
        await interaction.followup.send("This command can only be used in a team server.", ephemeral=True)
        return

    count, failed = 0, 0
    for member in guild.members:
        if member.bot:
            continue
        try:
            await member.send(message)
            count += 1
        except Exception:
            failed += 1
    await interaction.followup.send(f"Sent messages to {count} members. Failed to send to {failed} members.", ephemeral=True)


@tree.command(name="poll", description="Create a poll message and DM everyone")
async def poll(interaction: discord.Interaction):
    guild = interaction.guild
    channel = interaction.channel

    if guild is None or channel is None:
        await interaction.response.send_message("This command can only be used in a team server channel.", ephemeral=True)
        return

    guild_data = await get_guild_settings(guild.id)
    ff_role_id = guild_data.get("ff_role_id")
    if ff_role_id is None:
        await interaction.response.send_message("the friendly finder role wasn't set. use `/setffrole` to define it.", ephemeral=True)
        return

    ff_role = guild.get_role(ff_role_id)
    if ff_role not in interaction.user.roles:
        await interaction.response.send_message("You need friendly finder role..", ephemeral=True)
        return

    poll_msg = await channel.send("A poll for a friendly has been made, react down!")
    await poll_msg.add_reaction("✅")
    msg_link = f"https://discord.com/channels/{guild.id}/{channel.id}/{poll_msg.id}"

    await interaction.response.defer(ephemeral=True)

    count, failed = 0, 0
    dm_message = f"A poll for the friendly has been made, here is the link: {msg_link}"

    for member in guild.members:
        if member.bot:
            continue
        try:
            await member.send(dm_message)
            count += 1
        except Exception:
            failed += 1

    await interaction.followup.send(f"Poll created and messaged to {count} members. Failed to send to {failed} members.", ephemeral=True)


@tree.command(name="setateam", description="Set the pinged role as the A TEAM for this guild")
@app_commands.describe(role="The role to assign as A TEAM")
async def setateam(interaction: discord.Interaction, role: discord.Role):
    guild_id = interaction.guild.id
    await update_guild_setting(guild_id, "ateam_role_id", role.id)
    await interaction.response.send_message(f"Role {role.mention} set as A TEAM for this guild.", ephemeral=True)


@tree.command(name="setbteam", description="Set the pinged role as the B TEAM for this guild")
@app_commands.describe(role="The role to assign as B TEAM")
async def setbteam(interaction: discord.Interaction, role: discord.Role):
    guild_id = interaction.guild.id
    await update_guild_setting(guild_id, "bteam_role_id", role.id)
    await interaction.response.send_message(f"Role {role.mention} set as B TEAM for this guild.", ephemeral=True)


@tree.command(name="promote", description="Promote a user from B TEAM to A TEAM")
@app_commands.describe(user="The user to promote")
async def promote(interaction: discord.Interaction, user: discord.Member):
    guild_id = interaction.guild.id
    guild_data = await get_guild_settings(guild_id)
    a_role_id = guild_data.get("ateam_role_id")
    b_role_id = guild_data.get("bteam_role_id")

    if not a_role_id or not b_role_id:
        await interaction.response.send_message("A TEAM or B TEAM roles are not set for this guild.", ephemeral=True)
        return

    a_role = interaction.guild.get_role(a_role_id)
    b_role = interaction.guild.get_role(b_role_id)

    if b_role not in user.roles:
        await interaction.response.send_message(f"{user.mention} does not have the B TEAM role.", ephemeral=True)
        return

    try:
        await user.remove_roles(b_role)
        await user.add_roles(a_role)
        await interaction.response.send_message(f"{user.mention} has been promoted to A TEAM, congrats! 👏", ephemeral=False)
    except Exception as e:
        await interaction.response.send_message(f"Failed to promote {user.mention}: {e}", ephemeral=True)


@tree.command(name="demote", description="Demote a user from A TEAM to B TEAM")
@app_commands.describe(user="The user to demote")
async def demote(interaction: discord.Interaction, user: discord.Member):
    guild_id = interaction.guild.id
    guild_data = await get_guild_settings(guild_id)
    a_role_id = guild_data.get("ateam_role_id")
    b_role_id = guild_data.get("bteam_role_id")

    if not a_role_id or not b_role_id:
        await interaction.response.send_message("A TEAM or B TEAM roles are not set for this team server.", ephemeral=True)
        return

    a_role = interaction.guild.get_role(a_role_id)
    b_role = interaction.guild.get_role(b_role_id)

    if a_role not in user.roles:
        await interaction.response.send_message(f"{user.mention} does not have the A TEAM role.", ephemeral=True)
        return

    try:
        await user.remove_roles(a_role)
        await user.add_roles(b_role)
        await interaction.response.send_message(f"{user.mention} has been demoted to B TEAM, sad :(", ephemeral=False)
    except Exception as e:
        await interaction.response.send_message(f"Failed to demote {user.mention}: {e}", ephemeral=True)


@tree.command(name="setffrole", description="Set the Friendly Finder role for this guild")
@app_commands.describe(role="The role to assign as Friendly Finder")
async def setffrole(interaction: discord.Interaction, role: discord.Role):
    guild_id = interaction.guild.id
    await update_guild_setting(guild_id, "ff_role_id", role.id)
    await interaction.response.send_message(f"Role {role.mention} set as Friendly Finder for this team server.", ephemeral=True)


@tree.command(name="promotetoff", description="Give the Friendly Finder role to a user")
@app_commands.describe(user="The user to promote to Friendly Finder")
async def promotetoff(interaction: discord.Interaction, user: discord.Member):
    guild_id = interaction.guild.id
    guild_data = await get_guild_settings(guild_id)
    ff_role_id = guild_data.get("ff_role_id")
    if ff_role_id is None:
        await interaction.response.send_message("Le rôle Friendly Finder n'a pas été configuré. Utilisez `/setffrole` pour le définir.", ephemeral=True)
        return

    ff_role = interaction.guild.get_role(ff_role_id)

    if ff_role in user.roles:
        await interaction.response.send_message(f"{user.mention} a déjà le rôle Friendly Finder.", ephemeral=True)
        return

    try:
        await user.add_roles(ff_role)
        await interaction.response.send_message(f"{user.mention} a reçu le rôle Friendly Finder.", ephemeral=False)
    except Exception as e:
        await interaction.response.send_message(f"Impossible de donner le rôle Friendly Finder à {user.mention}: {e}", ephemeral=True)

@tree.command(name="schedule")
@app_commands.describe(date="Format: DD/MM/YYYY", time="Format: HH:MM", opponent="Name of the opponent", league="Optional league name")
async def schedule(interaction: discord.Interaction, date: str, time: str, opponent: str, league: str = "None"):
    try:
        dt = datetime.datetime.strptime(f"{date} {time}", "%d/%m/%Y %H:%M")
    except ValueError:
        await interaction.response.send_message("Invalid date or time format. Use DD/MM/YYYY and HH:MM.", ephemeral=True)
        return

    match_doc = {
        "guild_id": interaction.guild.id,
        "date": date,
        "time": time,
        "opponent": opponent,
        "league": league,
        "created_by": interaction.user.id
    }
    matches_col.insert_one(match_doc)

    embed = discord.Embed(title="Scheduled Match", color=discord.Color.blue())
    embed.add_field(name="Date", value=date, inline=True)
    embed.add_field(name="Time", value=time, inline=True)
    embed.add_field(name="Opponent", value=opponent, inline=False)
    embed.add_field(name="League", value=league, inline=False)
    embed.set_footer(text=f"Scheduled by {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)

@tree.command(name="listmatches")
async def list_matches(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    matches = list(matches_col.find({"guild_id": guild_id}))

    if not matches:
        await interaction.response.send_message("No scheduled matches found.", ephemeral=True)
        return

    embed = discord.Embed(title="Scheduled Matches", color=discord.Color.dark_red())
    for match in matches:
        embed.add_field(name=f"{match['date']} at {match['time']}", value=f"Opponent: {match['opponent']} | League: {match['league']}", inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="roaster")
@app_commands.describe(team="A or B")
async def roaster(interaction: discord.Interaction, team: str):
    team = team.upper()
    if team not in ["A", "B"]:
        await interaction.response.send_message("Invalid team. Please use 'A' or 'B'.", ephemeral=True)
        return

    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("This command must be used in a team server.", ephemeral=True)
        return

    settings = db['guild_settings'].find_one({"guild_id": str(guild.id)})
    role_id = settings.get("ateam_role_id" if team == "A" else "bteam_role_id")

    if role_id is None:
        await interaction.response.send_message(f"The {team} team role has not been set.", ephemeral=True)
        return

    role = guild.get_role(role_id)
    members = [m.mention for m in role.members] if role else []
    roster = "\n".join(members) if members else "No members in this team."

    embed = discord.Embed(title=f"{team} Team Roster", description=roster, color=discord.Color.purple())
    await interaction.response.send_message(embed=embed)

@tree.command(name="feedback")
@app_commands.describe(message="Your feedback to admins")
async def feedback(interaction: discord.Interaction, message: str):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("This command must be used in a team server.", ephemeral=True)
        return

    count = 0
    for member in guild.members:
        if member.guild_permissions.administrator and not member.bot:
            try:
                await member.send(f"Feedback from {interaction.user.mention} in {guild.name}:\n{message}")
                count += 1
            except:
                continue
    await interaction.response.send_message(f"Feedback sent to {count} admin(s).", ephemeral=True)

bot.run(TOKEN)

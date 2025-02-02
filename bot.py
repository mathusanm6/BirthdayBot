import datetime
import discord
import os
import random

from discord.ext import commands, tasks
from dotenv import load_dotenv
from json_helper import load_json, save_json

# Load environment variables from .env file
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Activate necessary intents
intents = discord.Intents.default()
intents.message_content = True  # To access message content if needed
intents.guilds = True  # To interact with servers
intents.members = True  # To access member information

bot = commands.Bot(command_prefix="!", intents=intents)

# ========================== Load data ==========================

data_dir = "data"

# Create a data directory if it doesn't exist
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

birthdays_file = os.path.join(data_dir, "birthdays.json")
config_file = os.path.join(data_dir, "config.json")

# The birthdays.json file should have a structure like:
# { guild_id: { user_id: "DD-MM", ... }, ... }
birthdays = load_json(birthdays_file)
# The config.json file should have a structure like:
# { guild_id: { "birthday_channel": channel_id, ... }, ... }
config = load_json(config_file)

# ============== Load resources (GIFs and messages) ==============

resources_dir = "resources"
birthday_messages_file = os.path.join(resources_dir, "birthday_messages.json")
gifs_file = os.path.join(resources_dir, "gifs.json")

# The birthday_messages.json in resources should have a structure like:
# { "BIRTHDAY_MESSAGES": [ "message1", "message2", ... ] }
resources_birthday_data = load_json(birthday_messages_file)
BIRTHDAY_MESSAGES = resources_birthday_data.get("BIRTHDAY_MESSAGES", [])

# The gifs.json in resources should have a structure like:
# { "GIFS": [ "gif_url1", "gif_url2", ... ] }
resources_gif_data = load_json(gifs_file)
GIFS = resources_gif_data.get("GIFS", [])

# ===================== Bot events ==========================


@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user}")
    try:
        await bot.tree.sync()
        print("Commandes slash synchronisées avec succès.")
    except Exception as e:
        print(f"Erreur lors de la synchronisation des commandes : {e}")
    check_birthdays.start()
    await check_birthdays()


# ======================= Bot commands ========================


@bot.tree.command(name="set_birthday", description="Set your birthday (format DD-MM)")
async def set_birthday(interaction: discord.Interaction, date: str):
    """Allows a user to record their birthday."""
    if not interaction.guild:
        await interaction.response.send_message(
            "Cette commande ne peut être utilisée que sur un serveur.", ephemeral=True
        )
        return
    try:
        datetime.datetime.strptime(date, "%d-%m")
    except ValueError:
        await interaction.response.send_message(
            "❌ Format invalide ! Utilise le format DD-MM (ex : 20-05).", ephemeral=True
        )
        return
    guild_id = str(interaction.guild.id)
    if guild_id not in birthdays:
        birthdays[guild_id] = {}
    birthdays[guild_id][str(interaction.user.id)] = date
    save_json(birthdays_file, birthdays)
    await interaction.response.send_message(
        f"🎂 {interaction.user.mention}, ton anniversaire a été enregistré pour le {date} !",
        ephemeral=True,
    )


@bot.tree.command(
    name="set_birthday_channel",
    description="Set THIS channel for birthday announcements",
)
async def set_birthday_channel(interaction: discord.Interaction):
    """Configures the current channel as the birthday announcement channel."""
    if not interaction.guild:
        await interaction.response.send_message(
            "Cette commande ne peut être utilisée que sur un serveur.", ephemeral=True
        )
        return
    guild_id = str(interaction.guild.id)
    if guild_id not in config:
        config[guild_id] = {}
    config[guild_id]["birthday_channel"] = interaction.channel.id
    save_json(config_file, config)
    await interaction.response.send_message(
        f"🎉 Ce salon ({interaction.channel.mention}) est désormais configuré pour les annonces d'anniversaire.",
        ephemeral=True,
    )


@bot.tree.command(name="upcoming_birthdays", description="List upcoming birthdays")
async def upcoming_birthdays(interaction: discord.Interaction):
    """Displays a list of upcoming birthdays for the server."""
    if not interaction.guild:
        await interaction.response.send_message(
            "Cette commande ne peut être utilisée que sur un serveur.", ephemeral=True
        )
        return
    guild_id = str(interaction.guild.id)
    today = datetime.datetime.utcnow().date()
    upcoming = []
    if guild_id in birthdays:
        for user_id, bday_str in birthdays[guild_id].items():
            try:
                day, month = map(int, bday_str.split("-"))
                birthday_this_year = datetime.date(today.year, month, day)
                if birthday_this_year < today:
                    next_birthday = datetime.date(today.year + 1, month, day)
                else:
                    next_birthday = birthday_this_year
                delta = (next_birthday - today).days
                upcoming.append((delta, next_birthday, user_id))
            except Exception as e:
                print(
                    f"Erreur pour l'utilisateur {user_id} avec la date {bday_str}: {e}"
                )
    if not upcoming:
        await interaction.response.send_message(
            "Aucun anniversaire n'est enregistré.", ephemeral=True
        )
        return
    upcoming.sort(key=lambda x: x[0])
    embed = discord.Embed(
        title="🎉 Anniversaires à venir",
        description="Voici la liste des anniversaires à venir :",
        color=discord.Color.blue(),
    )
    for delta, next_birthday, user_id in upcoming:
        try:
            user = await bot.fetch_user(int(user_id))
            username = user.name
        except Exception:
            username = f"Utilisateur inconnu ({user_id})"
        formatted_date = next_birthday.strftime("%d/%m")
        embed.add_field(
            name=username,
            value=f"Le **{formatted_date}** (dans **{delta}** jours)",
            inline=False,
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(
    name="send_test_announcement",
    description="Send a test birthday announcement in this channel",
)
@discord.app_commands.checks.has_permissions(administrator=True)
async def send_test_announcement(interaction: discord.Interaction):
    """Sends a test birthday announcement in the current channel (only if this channel is configured)."""
    if not interaction.guild:
        await interaction.response.send_message(
            "Cette commande ne peut être utilisée que sur un serveur.", ephemeral=True
        )
        return
    guild_id = str(interaction.guild.id)
    if (
        guild_id not in config
        or config[guild_id].get("birthday_channel") != interaction.channel.id
    ):
        await interaction.response.send_message(
            "❌ Ce salon n'est pas configuré pour les annonces d'anniversaire. Utilise la commande /set_birthday_channel ici.",
            ephemeral=True,
        )
        return
    admin_user = interaction.user
    gif_url = random.choice(GIFS)
    message_text = random.choice(BIRTHDAY_MESSAGES).format(user=admin_user.mention)
    embed = discord.Embed(description=message_text, color=discord.Color.green())
    embed.set_image(url=gif_url)
    try:
        msg = await interaction.channel.send(embed=embed)
        # Create a thread to collect wishes with an @everyone ping
        thread = await msg.create_thread(
            name=f"Test - Souhaits pour {admin_user.name}", auto_archive_duration=1440
        )
        await thread.send(
            "@everyone Bienvenue dans ce fil de discussion de test pour souhaiter un joyeux anniversaire !"
        )
        await interaction.response.send_message(
            "✅ Message de test envoyé avec succès.", ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"❌ Une erreur est survenue lors de l'envoi du message de test : {e}",
            ephemeral=True,
        )


@bot.tree.command(
    name="remove_birthday_channel",
    description="Remove birthday channel configuration for this server",
)
@discord.app_commands.checks.has_permissions(administrator=True)
async def remove_birthday_channel(interaction: discord.Interaction):
    """
    Removes only the birthday announcement channel configuration for this server.
    The birthday records in birthdays.json remain intact.
    """
    if not interaction.guild:
        await interaction.response.send_message(
            "Cette commande ne peut être utilisée que sur un serveur.", ephemeral=True
        )
        return
    guild_id = str(interaction.guild.id)
    if guild_id in config and "birthday_channel" in config[guild_id]:
        del config[guild_id]["birthday_channel"]
        save_json(config_file, config)
        await interaction.response.send_message(
            "✅ La configuration du salon d'annonces a été supprimée avec succès.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            "Aucune configuration de salon d'annonces n'a été trouvée pour ce serveur.",
            ephemeral=True,
        )


@bot.tree.command(
    name="remove_birthday_data", description="Remove all birthday data for this server"
)
@discord.app_commands.checks.has_permissions(administrator=True)
async def remove_birthday_data(interaction: discord.Interaction):
    """
    Explicitly removes all birthday data for this server.
    This clears the birthday records from birthdays.json (leaving the channel configuration intact).
    """
    if not interaction.guild:
        await interaction.response.send_message(
            "Cette commande ne peut être utilisée que sur un serveur.", ephemeral=True
        )
        return
    guild_id = str(interaction.guild.id)
    if guild_id in birthdays:
        del birthdays[guild_id]
        save_json(birthdays_file, birthdays)
        await interaction.response.send_message(
            "✅ Les données d'anniversaire pour ce serveur ont été supprimées avec succès.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            "Aucune donnée d'anniversaire n'a été trouvée pour ce serveur.",
            ephemeral=True,
        )


@bot.tree.command(name="help", description="Display help message")
async def help_command(interaction: discord.Interaction):
    """Displays a help message with a list of available commands in a nicely formatted embed."""
    is_admin = interaction.user.guild_permissions.administrator

    embed = discord.Embed(
        title="🎉 Birthday Bot Help",
        description="Voici la liste des commandes disponibles:",
        color=discord.Color.blue(),
    )

    # User commands
    embed.add_field(
        name="/set_birthday <date>",
        value="Enregistre ton anniversaire (format: JJ-MM) 🎂",
        inline=False,
    )
    embed.add_field(
        name="/upcoming_birthdays",
        value="Affiche la liste des anniversaires à venir.",
        inline=False,
    )

    # Admin commands
    if is_admin:
        embed.add_field(
            name="/send_test_announcement",
            value="Envoie un message de test pour les annonces (Admin uniquement) 🔧",
            inline=False,
        )
        embed.add_field(
            name="/set_birthday_channel",
            value="Configure ce salon pour les annonces d'anniversaire (Admin uniquement) 🎉",
            inline=False,
        )
        embed.add_field(
            name="/remove_birthday_channel",
            value="Supprime la configuration du salon d'annonces (Admin uniquement)",
            inline=False,
        )
        embed.add_field(
            name="/remove_birthday_data",
            value="Supprime toutes les données d'anniversaire pour ce serveur (Admin uniquement)",
            inline=False,
        )

    # Always available command
    embed.add_field(name="/help", value="Affiche ce message d'aide.", inline=False)

    embed.set_footer(text="Merci d'utiliser Birthday Bot!")

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ===================== Birthday check ========================


@tasks.loop(time=datetime.time(hour=0, minute=0))
async def check_birthdays():
    # Get today's date in "DD-MM" format
    today = datetime.datetime.utcnow().strftime("%d-%m")
    for guild_id, guild_config in config.items():
        channel_id = guild_config.get("birthday_channel")
        if not channel_id:
            print(f"Aucun salon d'anniversaire configuré pour le serveur {guild_id}.")
            continue
        channel = bot.get_channel(channel_id)
        if not channel:
            print(
                f"L'ID du salon dans la configuration est invalide pour le serveur {guild_id}."
            )
            continue
        if guild_id not in birthdays:
            continue
        for user_id, bday in birthdays[guild_id].items():
            if bday == today:
                try:
                    user = await bot.fetch_user(int(user_id))
                except Exception as e:
                    print(
                        f"Erreur lors de la récupération de l'utilisateur {user_id} : {e}"
                    )
                    continue
                gif_url = random.choice(GIFS)
                message_text = random.choice(BIRTHDAY_MESSAGES).format(
                    user=user.mention
                )
                embed = discord.Embed(
                    description=message_text, color=discord.Color.green()
                )
                embed.set_image(url=gif_url)
                try:
                    msg = await channel.send(embed=embed)
                    thread = await msg.create_thread(
                        name=f"Souhaits pour {user.name}", auto_archive_duration=1440
                    )
                    await thread.send(
                        "@everyone Bienvenue dans ce fil de discussion pour souhaiter un joyeux anniversaire !"
                    )
                except Exception as e:
                    print(f"Impossible de créer un fil pour {user.name} : {e}")


bot.run(TOKEN)

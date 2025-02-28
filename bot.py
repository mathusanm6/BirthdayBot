import datetime
import discord
import os
import random

from discord.ext import commands, tasks
from dotenv import load_dotenv
from json_helper import load_json, save_json

# Load environment variables from .env file
load_dotenv(".env")
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
# { guild_id: { user_id: "DD/MM", ... }, ... }
birthdays = load_json(birthdays_file)
# The config.json file should have a structure like:
# { guild_id: { "birthday_channel": channel_id, ... }, ... }
config = load_json(config_file)

# =================== Load resources (GIFs and messages) ===================

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

# ========================== Define the /birthday Command Group ==========================

birthday = discord.app_commands.Group(
    name="birthday", description="Commandes liées aux anniversaires"
)


# -------- /birthday set DD/MM --------
@birthday.command(name="set", description="Enregistre ton anniversaire (format: DD/MM)")
async def birthday_set(interaction: discord.Interaction, date: str):
    if not interaction.guild:
        await interaction.response.send_message(
            "Cette commande ne peut être utilisée que sur un serveur.", ephemeral=True
        )
        return
    try:
        datetime.datetime.strptime(date, "%d/%m")
    except ValueError:
        await interaction.response.send_message(
            "❌ Format invalide ! Utilise le format DD/MM (ex : 20/05).", ephemeral=True
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


# -------- /birthday show --------
@birthday.command(name="show", description="Affiche ton anniversaire enregistré")
async def birthday_show(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message(
            "Cette commande ne peut être utilisée que sur un serveur.", ephemeral=True
        )
        return
    guild_id = str(interaction.guild.id)
    user_bday = birthdays.get(guild_id, {}).get(str(interaction.user.id))
    if user_bday:
        await interaction.response.send_message(
            f"🎂 Ton anniversaire est enregistré pour le {user_bday}.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "❌ Aucun anniversaire enregistré pour toi.", ephemeral=True
        )


# -------- /birthday all --------
@birthday.command(
    name="all",
    description="Affiche tous les anniversaires enregistrés sur le serveur",
)
async def birthday_all(interaction: discord.Interaction):
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
                day, month = map(int, bday_str.split("/"))
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
            "Aucun anniversaire n'est enregistré sur ce serveur.", ephemeral=True
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
        day_text = "jour" if delta == 1 else "jours"
        embed.add_field(
            name=username,
            value=f"Le **{formatted_date}** (dans **{delta}** {day_text})",
            inline=False,
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


# -------- /birthday set_channel (Admin only) --------
@birthday.command(
    name="set_channel",
    description="Configure ce salon pour les annonces d'anniversaire (Admin uniquement)",
)
@discord.app_commands.checks.has_permissions(administrator=True)
async def birthday_set_channel(interaction: discord.Interaction):
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
        f"🎉 Ce salon ({interaction.channel.mention}) est configuré pour les annonces d'anniversaire.",
        ephemeral=True,
    )


# -------- /birthday remove_channel (Admin only) --------
@birthday.command(
    name="remove_channel",
    description="Supprime la configuration du salon d'annonces (Admin uniquement)",
)
@discord.app_commands.checks.has_permissions(administrator=True)
async def birthday_remove_channel(interaction: discord.Interaction):
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
            "✅ La configuration du salon d'annonces a été supprimée.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "Aucune configuration de salon d'annonces trouvée pour ce serveur.",
            ephemeral=True,
        )


# -------- Confirmation View for /birthday announce --------
class ConfirmAnnouncementView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        interaction: discord.Interaction,
        target: discord.Member,
    ):
        super().__init__(timeout=60)
        self.bot = bot
        self.interaction = interaction
        self.target = target  # The member to announce the birthday for
        self.value = None

    @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # Only the command invoker may confirm.
        if interaction.user != self.interaction.user:
            await interaction.response.send_message(
                "Tu n'as pas la permission de confirmer.", ephemeral=True
            )
            return

        await interaction.response.defer()
        self.value = True

        guild_id = str(self.interaction.guild.id)
        channel_id = config.get(guild_id, {}).get("birthday_channel")
        if not channel_id:
            await interaction.followup.send(
                "❌ Aucun salon d'annonces configuré.", ephemeral=True
            )
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            await interaction.followup.send(
                "❌ Salon d'annonces introuvable.", ephemeral=True
            )
            return

        if not self.target:
            await interaction.followup.send(
                "❌ Aucun membre spécifié pour l'annonce. Veuillez réessayer avec un membre.",
                ephemeral=True,
            )
            return

        gif_url = random.choice(GIFS)
        user_display = self.target.mention
        message_text = random.choice(BIRTHDAY_MESSAGES).format(user=user_display)
        embed = discord.Embed(description=message_text, color=discord.Color.green())
        embed.set_image(url=gif_url)

        try:
            msg = await channel.send(embed=embed)
            thread_name = f"Souhaits pour {self.target.name}"
            thread = await msg.create_thread(
                name=thread_name, auto_archive_duration=1440
            )
            await thread.send(
                "@everyone Bienvenue dans ce fil de discussion pour souhaiter un joyeux anniversaire !"
            )
            await interaction.followup.send(
                "✅ Message envoyé avec succès.", ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Erreur lors de l'envoi: {e}", ephemeral=True
            )

        self.stop()

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.interaction.user:
            await interaction.response.send_message(
                "Tu n'as pas la permission d'annuler.", ephemeral=True
            )
            return

        self.value = False
        self.stop()
        await interaction.response.send_message(
            "Annulation de l'envoi de l'annonce.", ephemeral=True
        )


# -------- /birthday announce [membre] (Admin only) --------
@birthday.command(
    name="announce",
    description=(
        "Annonce l'anniversaire d'un membre et ouvre un fil de discussion. (Admin uniquement)"
    ),
)
@discord.app_commands.checks.has_permissions(administrator=True)
async def birthday_announce(interaction: discord.Interaction, user: discord.Member):
    if not interaction.guild:
        await interaction.response.send_message(
            "Cette commande ne peut être utilisée que sur un serveur.", ephemeral=True
        )
        return

    guild_id = str(interaction.guild.id)
    configured_channel = config.get(guild_id, {}).get("birthday_channel")
    if configured_channel != interaction.channel.id:
        await interaction.response.send_message(
            "❌ Ce salon n'est pas configuré pour les annonces d'anniversaire. Utilise /birthday set_channel ici.",
            ephemeral=True,
        )
        return

    # Determine the target for the announcement.
    if user is not None:
        if user.id == bot.user.id:
            # The admin provided the bot itself.
            # Announce the bot's birthday and record today's date if not already set.
            target = bot.user
            if guild_id not in birthdays:
                birthdays[guild_id] = {}
            if str(bot.user.id) not in birthdays[guild_id]:
                today = datetime.datetime.utcnow().strftime("%d/%m")
                birthdays[guild_id][str(bot.user.id)] = today
                save_json(birthdays_file, birthdays)
        else:
            # Announce for the specified user.
            target = user

    # Show a confirmation prompt before sending the announcement.
    view = ConfirmAnnouncementView(bot, interaction, target=target)
    await interaction.response.send_message(
        "⚠️ Veuillez confirmer l'envoi de l'annonce d'anniversaire.",
        view=view,
        ephemeral=True,
    )


# -------- /birthday help --------
@birthday.command(
    name="help", description="Affiche l'aide pour les commandes d'anniversaire"
)
async def birthday_help(interaction: discord.Interaction):
    is_admin = interaction.user.guild_permissions.administrator

    embed = discord.Embed(
        title="🎉 Aide - Birthday Bot",
        description="Voici la liste des commandes disponibles:",
        color=discord.Color.blue(),
    )

    # User commands
    embed.add_field(
        name="/birthday set <date>",
        value="Enregistre ton anniversaire (format: JJ/MM) 🎂",
        inline=False,
    )
    embed.add_field(
        name="/birthday show",
        value="Affiche ton anniversaire enregistré.",
        inline=False,
    )
    embed.add_field(
        name="/birthday all",
        value="Affiche tous les anniversaires enregistrés sur le serveur.",
        inline=False,
    )

    # Admin-only commands
    if is_admin:
        embed.add_field(
            name="/birthday set_channel",
            value="Configure ce salon pour les annonces d'anniversaire. (Admin uniquement)",
            inline=False,
        )
        embed.add_field(
            name="/birthday remove_channel",
            value="Supprime la configuration du salon d'annonces. (Admin uniquement)",
            inline=False,
        )
        embed.add_field(
            name="/birthday announce [member]",
            value=(
                "Envoie une annonce pour l'anniversaire d'un membre. "
                "Un dialogue de confirmation s'affiche avant l'envoi. (Admin uniquement)"
            ),
            inline=False,
        )

    embed.add_field(
        name="/birthday help", value="Affiche ce message d'aide.", inline=False
    )
    embed.set_footer(text="Merci d'utiliser Birthday Bot!")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ========================== Birthday Check Task ==========================
@tasks.loop(time=datetime.time(hour=0, minute=0))
async def check_birthdays():
    # Get today's date in "DD/MM" format
    today = datetime.datetime.utcnow().strftime("%d/%m")
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
                    print(f"Erreur lors de la récupération du membre {user_id} : {e}")
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


@bot.event
async def on_ready():
    print(f"Connected as {bot.user}")
    try:
        # Clear all existing commands
        bot.tree.clear_commands(guild=None)
        # Add the birthday command group to all guilds
        for guild in bot.guilds:
            bot.tree.add_command(birthday, guild=discord.Object(id=guild.id))
            await bot.tree.sync(guild=discord.Object(id=guild.id))
    except Exception as e:
        print(f"Error during guild-specific command sync: {e}")
    check_birthdays.start()


bot.run(TOKEN)

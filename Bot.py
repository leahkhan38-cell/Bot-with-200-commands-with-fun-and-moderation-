import os, sys, sqlite3, time, re, datetime
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from datetime import timedelta
from collections import defaultdict

# ======================
# ENV + AUTO SETUP
# ======================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
MOD_LOG_CHANNEL = os.getenv("MOD_LOG_CHANNEL", "mod-logs")

os.makedirs("data", exist_ok=True)

# Database
db = sqlite3.connect("data/mod.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    moderator_id INTEGER,
    action TEXT,
    reason TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS warnings (
    user_id INTEGER PRIMARY KEY,
    count INTEGER
)
""")
db.commit()

# Restart audit log
RESTART_LOG = "data/restart.log"
if not os.path.exists(RESTART_LOG):
    with open(RESTART_LOG, "w") as f:
        f.write("Restart Audit Log\n=================\n")

def log_restart(user, success):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = "SUCCESS" if success else "FAIL"
    with open(RESTART_LOG, "a") as f:
        f.write(f"[{timestamp}] {user} → {result}\n")

# ======================
# DATABASE HELPERS
# ======================
def add_case(u, m, a, r):
    cur.execute("INSERT INTO cases VALUES (NULL,?,?,?,?)",(u,m,a,r))
    db.commit()
    return cur.lastrowid

def warn_user(uid):
    cur.execute("INSERT INTO warnings VALUES (?,1) ON CONFLICT(user_id) DO UPDATE SET count=count+1",(uid,))
    db.commit()

def get_warns(uid):
    cur.execute("SELECT count FROM warnings WHERE user_id=?",(uid,))
    r=cur.fetchone()
    return r[0] if r else 0

def clear_warns(uid):
    cur.execute("DELETE FROM warnings WHERE user_id=?",(uid,))
    db.commit()

# ======================
# BOT SETUP
# ======================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def setup_hook():
    await bot.tree.sync()

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

def log_channel(guild):
    return discord.utils.get(guild.text_channels, name=MOD_LOG_CHANNEL)

async def log(guild, msg):
    ch = log_channel(guild)
    if ch:
        await ch.send(msg)

# ======================
# AUTOMOD
# ======================
msg_log = defaultdict(list)
LINK = re.compile(r"https?://")

@bot.event
async def on_message(m):
    if m.author.bot or not m.guild:
        return
    now = time.time()
    msg_log[m.author.id] = [t for t in msg_log[m.author.id] if now - t < 5]
    msg_log[m.author.id].append(now)

    # Spam
    if len(msg_log[m.author.id]) >= 5:
        await m.delete()
        await m.author.timeout(timedelta(minutes=5), reason="Spam")
        add_case(m.author.id, bot.user.id, "AUTOMOD_MUTE", "Spam")
        return

    # Links
    if LINK.search(m.content) and not m.author.guild_permissions.manage_messages:
        await m.delete()
        return

    # Caps
    if len(m.content) > 10:
        caps = sum(1 for c in m.content if c.isupper())
        if caps / len(m.content) > 0.7:
            await m.delete()
            return

    # Mass mentions
    if len(m.mentions) >= 5:
        await m.delete()
        await m.author.timeout(timedelta(minutes=10), reason="Mass mentions")
        add_case(m.author.id, bot.user.id, "AUTOMOD_MUTE", "Mass mentions")

    await bot.process_commands(m)

# ======================
# MOD COMMANDS
# ======================
@bot.tree.command()
@app_commands.checks.has_permissions(ban_members=True)
async def ban(i, member: discord.Member, reason: str):
    await member.ban(reason=reason)
    cid = add_case(member.id, i.user.id, "BAN", reason)
    await log(i.guild, f"🔨 {member} banned | Case #{cid}")
    await i.response.send_message(f"Banned. Case #{cid}")

@bot.tree.command()
@app_commands.checks.has_permissions(ban_members=True)
async def softban(i, member: discord.Member, reason: str):
    await member.ban(reason=reason, delete_message_days=7)
    await member.unban()
    cid = add_case(member.id, i.user.id, "SOFTBAN", reason)
    await i.response.send_message(f"Softbanned. Case #{cid}")

@bot.tree.command()
@app_commands.checks.has_permissions(kick_members=True)
async def kick(i, member: discord.Member, reason: str):
    await member.kick(reason=reason)
    cid = add_case(member.id, i.user.id, "KICK", reason)
    await i.response.send_message(f"Kicked. Case #{cid}")

@bot.tree.command()
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(i, member: discord.Member, minutes: int, reason: str):
    await member.timeout(timedelta(minutes=minutes), reason=reason)
    cid = add_case(member.id, i.user.id, "MUTE", reason)
    await i.response.send_message(f"Muted. Case #{cid}")

@bot.tree.command()
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute(i, member: discord.Member):
    await member.timeout(None)
    cid = add_case(member.id, i.user.id, "UNMUTE", "Timeout removed")
    await i.response.send_message(f"Unmuted. Case #{cid}")

@bot.tree.command()
@app_commands.checks.has_permissions(moderate_members=True)
async def warn(i, member: discord.Member, reason: str):
    warn_user(member.id)
    count = get_warns(member.id)
    cid = add_case(member.id, i.user.id, "WARN", reason)
    if count == 3:
        await member.timeout(timedelta(minutes=10), reason="Auto escalation")
    if count >= 5:
        await member.ban(reason="Auto escalation")
    await i.response.send_message(f"Warned. Total warnings: {count} | Case #{cid}")

@bot.tree.command()
@app_commands.checks.has_permissions(moderate_members=True)
async def warnings(i, member: discord.Member):
    await i.response.send_message(f"{member} has {get_warns(member.id)} warnings.", ephemeral=True)

@bot.tree.command()
@app_commands.checks.has_permissions(administrator=True)
async def clearwarnings(i, member: discord.Member):
    clear_warns(member.id)
    await i.response.send_message("Warnings cleared.")

@bot.tree.command()
@app_commands.checks.has_permissions(manage_messages=True)
async def purge(i, amount: int):
    await i.response.defer(ephemeral=True)
    deleted = await i.channel.purge(limit=amount)
    await i.followup.send(f"Deleted {len(deleted)} messages.", ephemeral=True)

@bot.tree.command()
@app_commands.checks.has_permissions(manage_channels=True)
async def lock(i):
    await i.channel.set_permissions(i.guild.default_role, send_messages=False)
    await i.response.send_message("Channel locked.")

@bot.tree.command()
@app_commands.checks.has_permissions(manage_channels=True)
async def unlock(i):
    await i.channel.set_permissions(i.guild.default_role, send_messages=True)
    await i.response.send_message("Channel unlocked.")

@bot.tree.command()
@app_commands.checks.has_permissions(manage_channels=True)
async def slowmode(i, seconds: int):
    await i.channel.edit(slowmode_delay=seconds)
    await i.response.send_message("Slowmode updated.")

# ======================
# APPEALS
# ======================
@bot.tree.command()
async def appeal(i, message: str):
    sent = 0
    for m in i.guild.members:
        if m.guild_permissions.moderate_members:
            try:
                await m.send(f"📨 Appeal from {i.user}\n\n{message}")
                sent += 1
            except:
                pass
    await i.response.send_message(f"Appeal sent to {sent} moderators.", ephemeral=True)

# ======================
# RESTART WITH PASSWORD
# ======================
class RestartModal(discord.ui.Modal, title="Confirm Restart"):
    password = discord.ui.TextInput(
        label="Restart Password",
        placeholder="Enter restart password",
        style=discord.TextStyle.short,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        if self.password.value != "Sigma":
            log_restart(interaction.user, False)
            await interaction.response.send_message("❌ Incorrect password.", ephemeral=True)
            return
        log_restart(interaction.user, True)
        await interaction.response.send_message("♻️ Restarting bot…")
        os.execv(sys.executable, ["python"] + sys.argv)

class RestartView(discord.ui.View):
    @discord.ui.button(label="Restart Bot", style=discord.ButtonStyle.danger)
    async def restart(self, interaction: discord.Interaction, _):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return
        await interaction.response.send_modal(RestartModal())

@bot.tree.command()
@app_commands.checks.has_permissions(administrator=True)
async def restart(i):
    await i.response.send_message(
        "⚠️ Click below to restart the bot.",
        view=RestartView(),
        ephemeral=True
    )

# ======================
# RUN
# ======================
bot.run(TOKEN)


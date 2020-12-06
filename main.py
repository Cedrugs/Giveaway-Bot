from discord.ext.commands import Bot

bot = Bot(command_prefix=".", case_insensitive=True)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}.")

if __name__ == "__main__":
    try:
        bot.load_extension('cogs.giveaway')
    except Exception as exc:
        print(exc)

bot.run('Nzg0OTk0MzU4ODUxNDAzODM2.X8xY9w.y_qF9e9pRn7DZBC07-4rvfVK2II')

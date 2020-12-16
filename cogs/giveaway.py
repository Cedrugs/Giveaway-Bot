from discord.ext import commands, tasks
from discord.ext.commands import Context
from db import Database
from dateutil import relativedelta

import asyncio
import datetime
import logging
import discord
import random


log = logging.getLogger(__name__)
db = Database("main.db")


class Giveaways(commands.Cog, name='Giveaway'):
    """Commands to control a giveaway."""

    def __init__(self, bot):
        self.bot = bot
        self.determine_winner.start()

    def cog_unload(self):
        self.determine_winner.cancel()

    @staticmethod
    def convert(time):
        pos = ["s", "m", "h", "d"]
        time_dict = {"s": 1, "m": 60, "h": 3600, "d": 3600 * 24}
        unit = time[-1]
        if unit not in pos:
            return -1
        try:
            val = int(time[:-1])
        except Exception as exc:
            print(exc)
            return -2
        return val * time_dict[unit]

    @staticmethod
    def get_id(num_range: int):
        return random.randint(100, num_range)

    @staticmethod
    async def add_giveaway(ctx, channel: discord.TextChannel, time: int, prize: str, gid: int, quickg=False):
        e = discord.Embed(color=ctx.author.color, title="Giveaway Time!", description=prize)
        end = datetime.datetime.utcnow() + datetime.timedelta(seconds=time)
        e.add_field(name="Ends at:", value=str(end.strftime('%Y-%m-%d %H:%M:%S')))
        e.set_footer(text=f"Ends in {time}{' minutes' if quickg else ''} from now on.")
        cv_time = datetime.datetime.utcnow() + relativedelta.relativedelta(seconds=time)
        msg = await channel.send(embed=e)
        await msg.add_reaction("🎉")
        await db.autoexecute(
            "INSERT INTO giveaway(GuildID, ChannelID, MessageID, Prize, EndTime, GiveawayID) VALUES(?, ?, ?, ?, ?, ?)",
            ctx.guild.id, channel.id, msg.id, prize, cv_time.strftime('%Y-%m-%d %H:%M:%S'), gid
        )

    @staticmethod
    async def drop_giveaway(ctx: Context, gid: int):
        g_data = await db.record("SELECT * FROM giveaway WHERE GuildID = ? AND GiveawayID = ?", ctx.guild.id, gid)
        channel: discord.TextChannel = ctx.guild.get_channel(g_data[1])
        if channel:
            try:
                message = await channel.fetch_message(g_data[2])
                print(message)
                await message.delete()
            except discord.NotFound:
                pass
            except discord.Forbidden:
                pass
        await db.autoexecute("DELETE FROM giveaway WHERE GuildID = ? AND GiveawayID = ?", ctx.guild.id, gid)

    @tasks.loop(seconds=5)
    async def determine_winner(self):
        g_list = await db.recordall("SELECT * FROM giveaway")
        if not g_list:
            return
        for data in g_list:
            g_time = datetime.datetime.strptime(data[4], '%Y-%m-%d %H:%M:%S')
            if datetime.datetime.utcnow() >= g_time:
                try:
                    guild = self.bot.get_guild(data[0])
                    channel = guild.get_channel(data[1])
                    message = await channel.fetch_message(data[2])
                    user_list = [u for u in await message.reactions[0].users().flatten() if u != self.bot.user]
                    e = discord.Embed(color=discord.Color.red())

                    if len(user_list) == 0:
                        e.title = "There is no winner, nobody has reacted."
                        e.timestamp = datetime.datetime.utcnow()
                        e.set_footer(text=f'{self.bot.user.name}',
                                     icon_url=self.bot.user.avatar_url)
                        await channel.send(embed=e)
                    else:
                        winner = random.choice(user_list)
                        e.title = "Giveaway ended!"
                        e.description = f"You won: {data[3]}"
                        e.timestamp = datetime.datetime.utcnow()
                        e.set_footer(text=f'{self.bot.user.name}',
                                     icon_url=self.bot.user.avatar_url)
                        await channel.send(f"{winner.mention}", embed=e)
                except Exception as exc:
                    print(exc)
                finally:
                    await db.autoexecute(
                        "DELETE FROM giveaway WHERE GuildID = ? AND ChannelID = ? AND MessageID = ?",
                        data[0], data[1], data[2]
                    )

    @determine_winner.before_loop
    async def before_start(self):
        await self.bot.wait_until_ready()

    @commands.command(name="Giveaways", aliases=["quickgiv"])
    @commands.has_permissions(manage_messages=True)
    async def quickg(self, ctx, mins: int, *, prize: str):
        return await self.add_giveaway(ctx, ctx.channel, mins * 60, prize, self.get_id(10000), True)

    @commands.command(name="Giveaway")
    @commands.has_permissions(manage_messages=True)
    async def giveaway(self, ctx):
        e = discord.Embed(color=ctx.author.color)
        e.description = "Thanks for starting the automatic process. Let's start a giveaway!\n *(You have about 30 " \
                        "seconds to answer each question.)* "
        e.timestamp = datetime.datetime.utcnow()
        e.set_footer(text=f'{self.bot.user.name}',
                     icon_url=self.bot.user.avatar_url)
        await ctx.send(embed=e)

        questions = ["In which channel should the giveaway take place? :eyes:",
                     "How long should the giveaway last? (You can choose between `s/m/h/d`",
                     "What can you win?"]

        answers = []

        def check(m):
            return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

        for i in questions:
            await ctx.send(i)
            try:
                msg = await self.bot.wait_for('message', timeout=30.0, check=check)
            except asyncio.TimeoutError:
                await ctx.send("You did not answer the question in time. Please start the process again.")
                return
            else:
                answers.append(msg)  # append the message object instead of the content

        if not answers[0].raw_channel_mentions:
            return await ctx.send(
                f"You have not specified the channel correctly. Do it like this: {ctx.channel.mention} the next time."
            )
        channel = ctx.guild.get_channel(int(answers[0].raw_channel_mentions[0]))
        if not channel:  # In case smh the owner suddenly deletes the channel
            return await ctx.send(
                f"You have not specified the channel correctly. Do it like this: {ctx.channel.mention} the next time."
            )

        time = self.convert(answers[1].content)
        if time == -1:
            await ctx.send("You did not mention the time correct. Use `s/m/h/d`")
            return
        elif time == -2:
            await ctx.send(f"The time must be an integer. Please enter an integer next time.")
            return
        prize = answers[2].content

        await ctx.send(f"The giveaway will be hosted in the following channel: {channel.mention}"
                       f"It will last: {answers[1].content}.")

        # Instead of having 2 same function, we're about to combine it xD
        await self.add_giveaway(ctx, channel, time, prize, self.get_id(10000))

    @commands.command(aliases=['delgiv'])
    @commands.has_permissions(manage_messages=True)
    async def dropgiv(self, ctx, giveaway_id):
        await self.drop_giveaway(ctx, int(giveaway_id))
        await ctx.send(f"Giveaway with id `{giveaway_id}` has been deleted!")


def setup(bot):
    bot.add_cog(Giveaways(bot))
    log.info(f'Giveaway loaded!')

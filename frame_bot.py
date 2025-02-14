from twitchio.ext import commands
import sys, json, time
from datetime import date, datetime
from bot_api import *
from dust_db import *
from dust_scrape import *
from dggg import *
from pymongo import MongoClient


##################################################################################
# ARGUMENT INGESTION, VARIABLE INITIALIZATION AND JOIN
##################################################################################


# set prefix to first command line argument, or default to !
try:
    set_prefix = sys.argv[1]
except IndexError:
    print("no arguments, setting prefix to !")
    set_prefix = "!"

# list of channels to join
with open("./channels.json") as fp:
    channels = json.load(fp)


# check for command line arguments after prefix argument for additional channels to join
if sys.argv[2:]:
    for arg in sys.argv[2:]:
        channels["channel_names"].append(arg)
else:
    print("no additional channels")

print(
    f'Joining twitch channels {", ".join(channels["channel_names"])} with {set_prefix} set as command prefix.'
)

with open("./tokens.json") as fp:
    auth_token = json.load(fp)["twitch"]

db_client = MongoClient("mongodb://10.22.22.29:27017")

# open daily ryan contest data file
try:
    with open("./db/ryan.json") as fp:
        ryan_data = json.load(fp)
except:
    ryan_data = {}
    with open("./db/ryan.json", "w") as fp:
        json.dump(ryan_data, fp, indent=4)


##################################################################################
# BOT INITIALIZATION
##################################################################################


class Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            token=auth_token,
            prefix=set_prefix,
            initial_channels=channels["channel_names"],
            case_insensitive=True,
        )

    async def event_ready(self):

        print(
            f'Logged in as | {self.nick} at {datetime.now().strftime("%m/%d/%Y, %H:%M:%S")}'
        )

    # ignore incorrect command errors
    async def event_command_error(
        self, context: commands.Context, error: commands.errors.CommandNotFound
    ):
        pass

    async def event_message(self, message):
        # make start a global variable if it isn't already, for ryan stuff. this is bad, I know.  the whole ryan thing needs a re-think but it works for now
        global start
        # ignore own messages
        if message.echo:
            print(f"{message.channel} {message.content}")
            return
        # print chatter's successful command uses
        # if message.content.startswith(set_prefix):
        #     print(f'[{message.channel}]{message.author.name}: {message.content}')
        # more ryan stuff
        if message.author.name == "ryanhunter" and message.channel.name == "sajam":
            today = str(date.today())
            if today != ryan_data["date"]:
                start = time.time()
        await self.handle_commands(message)

    # commands start
    @commands.command()
    async def wtbdjoin(self, ctx: commands.Context, *, full_message=None):
        await self.join_channels([full_message])

    @commands.command()
    async def hello(self, ctx: commands.Context):
        if ctx.author.is_mod or ctx.author.name == "avaren":
            await ctx.reply(
                f"Hello {ctx.author.name} in {ctx.channel.name}.  I am alive. MrDestructoid"
            )
            print(self.connected_channels)

    @commands.command()
    async def troy(self, ctx: commands.Context):
        await ctx.send("OhMyDog")

    @commands.command()
    async def miso(self, ctx: commands.Context):
        await ctx.send("Wowee")

    @commands.command()
    async def ryan(self, ctx: commands.Context):
        global start, ryan_data
        if ctx.channel.name == "sajam":
            if "start" in globals():
                end = time.time()
                elapsed = end - start
                elapsed = round(elapsed, 5)
                try:
                    ryan_data["winners"][ctx.author.name]
                except KeyError:
                    ryan_data["winners"][ctx.author.name] = 0
                await ctx.send(
                    f"{ctx.author.name} won the daily ryan challenge in {elapsed} seconds. Wins: {ryan_data['winners'][ctx.author.name]+1}"
                )
                ryan_data["date"] = str(date.today())
                ryan_data["winners"][ctx.author.name] += 1
                if elapsed < ryan_data["record_time"]:
                    ryan_data["record_time"] = elapsed
                    ryan_data["record_holder"] = ctx.author.name
                    await ctx.send(f"A new record!  Congratulations {ctx.author.name}.")
                with open("./db/ryan.json", "w") as fp:
                    json.dump(ryan_data, fp, indent=4)
                del start

    @commands.command()
    async def ryanstats(self, ctx: commands.Context, *, full_message=None):
        global ryan_data
        if ctx.channel.name == "sajam":
            if full_message and full_message.split()[0] == "record":
                await ctx.send(
                    f"The current record holder is {ryan_data['record_holder']} with a time of {ryan_data['record_time']} seconds."
                )
            else:
                try:
                    ryan_data["winners"][ctx.author.name]
                except KeyError:
                    return
                await ctx.send(
                    f"@{ctx.author.name} You have won the Ryan challenge {ryan_data['winners'][ctx.author.name]} times."
                )

    @commands.command()
    async def fd(self, ctx: commands.Context, *, full_message=None):
        if ctx.channel.name in channels["fighter_channels"]:
            # prevent anyone but me from updating database notes from chat
            if "!add" in full_message and not ctx.author.is_mod:
                return
            # handle !fd help requests, common guess for help with the bot
            if full_message.split()[0] == "help":
                await ctx.send(
                    f'Format: !fd [character(partial ok)] [move name or input(partial ok)] [specified stat or "detail" for full move stats.  eg: !fd gio 2d startup, !fd ky stun dipper. visit docs.botdoin.com for more info. '
                )
                return
            await ctx.reply(parse_move(db_client, ctx.channel.name, full_message))

    @commands.command()
    async def fdupdate(self, ctx: commands.Context, *, full_message=None):
        if ctx.channel.name in channels["fighter_channels"]:
            # only allows streamer or me to scrape new data
            if ctx.author.name == ctx.channel.name or ctx.author.name == "avaren":
                # if no argument, scrape guilty gear strive
                if not full_message:
                    game = "ggst"
                else:
                    game = full_message.split()[0]
                await ctx.send(
                    f"Importing {game.upper()} data from the web to local database."
                )
                import_data(game)
                await ctx.send(f"{game.upper()} database refreshed.")

    @commands.command()
    async def fdreadme(self, ctx: commands.Context):
        if ctx.channel.name in channels["fighter_channels"]:
            if ctx.author.is_mod or ctx.author.name == "avaren":
                await ctx.send(
                    "Visit https://github.com/itsavaren/strive-frame-data-bot for documentation."
                )

    @commands.command()
    async def pokiw(self, ctx: commands.Context):
        if (
            ctx.author.name
            in [
                "avaren",
                "madroctos",
                "voidashe",
                "moopoke",
                "sajam",
                "flaskpotato",
                "kierke",
            ]
            or ctx.author.name == ctx.channel.name
        ):
            await ctx.send("pokiW")

    @commands.command()
    async def zoom(self, ctx: commands.Context):
        await ctx.send("voidas2Zoom")

    @commands.command()
    async def define(self, ctx: commands.Context, *, full_message=None):
        if ctx.channel.name in channels["complex_meme_channels"]:
            await ctx.send(define_word(full_message))

    @commands.command()
    async def glossary(self, ctx: commands.Context, *, full_message=None):
        if ctx.channel.name in channels["glossary_channels"]:
            await ctx.send(
                f"@{ctx.author.name}: https://glossary.infil.net/?t="
                + full_message.replace(" ", "+")
            )

    @commands.command()
    async def silksong(self, ctx: commands.Context):
        if ctx.channel.name in channels["simple_meme_channels"]:
            await ctx.send(f"Silksong is never coming out")

    @commands.command()
    async def translate(self, ctx: commands.Context, *, full_message=None):
        if ctx.channel.name in channels["complex_meme_channels"]:
            await ctx.send(translate(full_message))

    @commands.command()
    async def fishsong(self, ctx: commands.Context):
        if ctx.channel.name == "akafishperson":
            await ctx.send(
                f"✅ Verses don't rhyme  ✅ Wrong number of syllables  ✅ Performed with love  ✅ Must be an akaFishperson cover"
            )

    @commands.command()
    async def rank(self, ctx: commands.Context, *, full_message=None):
        if ctx.channel.name in channels["league_channels"]:
            if not full_message:
                if ctx.channel.name == "mrmouton":
                    full_message = "iammentallyill"
                if ctx.channel.name == "destiny":
                    return
            await ctx.send(f"@{ctx.author.name} {get_rank(full_message)}")

    @commands.command()
    async def lp(self, ctx: commands.Context, *, full_message=None):
        if ctx.channel.name in channels["league_channels"]:
            if not full_message:
                if ctx.channel.name == "mrmouton":
                    full_message = "iammentallyill"
                if ctx.channel.name == "destiny":
                    return
            await ctx.send(f"@{ctx.author.name} {get_rank(full_message)}")

    @commands.command()
    async def songid(self, ctx: commands.Context):
        if ctx.channel.name in channels["songid_channels"]:
            await ctx.send(f"@{ctx.author.name} {identify_song(ctx.channel.name)}")

    @commands.command()
    async def orcs(self, ctx: commands.Context):
        if ctx.channel.name in channels["simple_meme_channels"]:
            await ctx.send(f"SMOrc SMOrc SMOrc")

    @commands.command()
    async def bingus(self, ctx: commands.Context):
        if ctx.channel.name in channels["simple_meme_channels"]:
            await ctx.send(bingus_quote())

    @commands.command()
    async def wiki(self, ctx: commands.Context, *, full_message=None):
        if ctx.channel.name in channels["wiki_channels"]:
            await ctx.send(wiki_def(full_message)[0:490])

    cat_start = time.time()

    @commands.command()
    async def catfact(self, ctx: commands.Context):
        global cat_start
        if ctx.channel.name in channels["simple_meme_channels"]:
            if time.time() - cat_start > 600:
                await ctx.reply(cat_fact())
                cat_start = time.time()

    @commands.command()
    async def dg(self, ctx: commands.Context, *, full_message=None):
        if ctx.channel.name in channels["league_channels"]:
            if "blood" in full_message:
                await ctx.send(first_winrate("blood"))
            if "dragon" in full_message or "drake" in full_message:
                await ctx.send(first_winrate("drake"))
            if "winrate" in full_message:
                await ctx.send(solo_duo_winrate())
            else:
                await ctx.send(champ_winrate(select_champ(full_message)))

    @commands.command()
    async def dglive(self, ctx: commands.Context):
        if ctx.channel.name in channels["league_channels"]:
            await ctx.send(spec_check(ctx.channel.name))

    @commands.command()
    async def dgload(self, ctx: commands.Context, *, full_message=None):
        if ctx.channel.name in channels["league_channels"] and ctx.author.name in [
            "avaren",
            "kierke",
        ]:
            start_total = total_matches()
            await ctx.send("Attempting to get fresh matches.")
            load_history(full_message)
            end_total = total_matches()
            await ctx.send(f"Added {end_total - start_total} matches.")

    @commands.command()
    async def dgtotal(self, ctx: commands.Context):
        if ctx.channel.name in channels["league_channels"]:
            await ctx.send(f"Database contains {total_matches()} matches.")

    @commands.command()
    async def odds(self, ctx: commands.Context, *, full_message=None):
        if ctx.channel.name in channels["complex_meme_channels"]:
            if int(full_message):
                await ctx.send(
                    f"The odds of {full_message} pokemons in a row is 1 in {13**int(full_message)}, or {int(full_message)/13**int(full_message):.5f}%"
                )


bot = Bot()
bot.run()

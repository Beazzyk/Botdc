import discord
from discord.ext import commands
import yt_dlp as youtube_dl  # Używamy yt-dlp zamiast youtube-dl
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()  # Ładujemy zmienne środowiskowe z pliku .env

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
FFMPEG_PATH = os.getenv("FFMPEG_PATH")
print(f"FFMPEG_PATH: {FFMPEG_PATH}")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Konfiguracja yt-dlp
ytdl_format_options = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'quiet': True,
    'extractaudio': True,
    'noplaylist': False,  # Obsługa playlist
}

ffmpeg_options = {
    'options': '-vn',
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

queues = {}  # Słownik do przechowywania kolejek dla różnych serwerów


def get_queue(guild_id):
    if guild_id not in queues:
        queues[guild_id] = []
    return queues[guild_id]


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        except Exception as e:
            print(f"Błąd podczas pobierania danych z URL: {e}")
            return None

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(executable=FFMPEG_PATH, source=filename, **ffmpeg_options), data=data)


@bot.command(name="play", help="Dodaje utwór do kolejki i odtwarza.")
async def play(ctx, url):
    queue = get_queue(ctx.guild.id)

    if not ctx.author.voice:
        await ctx.send("Musisz być na kanale głosowym, aby użyć tej komendy.")
        return

    channel = ctx.author.voice.channel

    if ctx.voice_client is None:
        await channel.connect()

    async with ctx.typing():
        player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
        if player is None:
            await ctx.send("Nie udało się pobrać utworu. Sprawdź URL i spróbuj ponownie.")
            return

        queue.append({"player": player, "title": player.title})
        await ctx.send(f"Dodano do kolejki: {player.title}")

    if not ctx.voice_client.is_playing():
        await play_next(ctx)


async def play_next(ctx):
    queue = get_queue(ctx.guild.id)
    if queue:
        track = queue.pop(0)
        ctx.voice_client.play(track["player"], after=lambda e: bot.loop.create_task(play_next(ctx)))
        await ctx.send(f"Odtwarzanie: {track['title']}")


@bot.command(name="queue", help="Pokazuje kolejkę utworów.")
async def show_queue(ctx):
    queue = get_queue(ctx.guild.id)
    if not queue:
        await ctx.send("Kolejka jest pusta!")
    else:
        queue_list = "\n".join(f"{i+1}. {track['title']}" for i, track in enumerate(queue))
        await ctx.send(f"Obecna kolejka:\n{queue_list}")


@bot.command(name="skip", help="Pomija aktualny utwór.")
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Pominięto utwór.")
        await play_next(ctx)
    else:
        await ctx.send("Nie ma aktualnie odtwarzanego utworu.")


@bot.command(name="stop", help="Zatrzymuje muzykę i czyści kolejkę.")
async def stop(ctx):
    if ctx.voice_client:
        queue = get_queue(ctx.guild.id)
        queue.clear()
        await ctx.voice_client.disconnect()
        await ctx.send("Bot opuścił kanał głosowy i wyczyścił kolejkę.")
    else:
        await ctx.send("Bot nie jest na żadnym kanale głosowym.")


@bot.event
async def on_ready():
    print(f"Bot zalogowany jako {bot.user}")

if __name__ == "__main__":
    bot.run(TOKEN)


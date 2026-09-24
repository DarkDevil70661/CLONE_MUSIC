import asyncio
import os
import re
import shutil
import subprocess
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from py_yt import VideosSearch, Playlist
import aiohttp


API_URL = os.environ.get(
    "SHRUTI_API_URL",
    "https://api.shrutibots.site"
)

API_KEY = os.environ.get(
    "ShrutiBotsdHuzQt3bGAwymyxq8QcW",
    ""
)

DOWNLOAD_DIR = "downloads"


def time_to_seconds(time):
    stringt = str(time)
    return sum(
        int(x) * 60 ** i
        for i, x in enumerate(reversed(stringt.split(":")))
    )


def get_video_id(link: str) -> str:
    """
    Extract YouTube video ID from different YouTube URL formats.
    """

    if not link:
        return None

    link = str(link).strip()

    # Normal youtube.com/watch?v=
    match = re.search(
        r"(?:youtube\.com/watch\?v=|youtube\.com/shorts/|youtu\.be/)([A-Za-z0-9_-]{6,})",
        link
    )

    if match:
        return match.group(1)

    # If already a video ID
    if re.fullmatch(r"[A-Za-z0-9_-]{6,}", link):
        return link

    # Fallback for v= parameter
    if "v=" in link:
        video_id = link.split("v=", 1)[1].split("&", 1)[0]
        if video_id:
            return video_id

    return None


def get_ffmpeg_path():
    """
    Find ffmpeg installed by Heroku Apt buildpack.
    """

    return (
        shutil.which("ffmpeg")
        or "/app/.apt/usr/bin/ffmpeg"
        or "ffmpeg"
    )


def get_ffprobe_path():
    """
    Find ffprobe installed by Heroku Apt buildpack.
    """

    return (
        shutil.which("ffprobe")
        or "/app/.apt/usr/bin/ffprobe"
        or "ffprobe"
    )


def is_valid_media_file(file_path: str) -> bool:
    """
    Check whether the downloaded file is actually a readable
    media file using ffprobe.
    """

    if not file_path:
        return False

    if not os.path.exists(file_path):
        return False

    try:
        if os.path.getsize(file_path) < 1024:
            return False
    except Exception:
        return False

    try:
        ffprobe = get_ffprobe_path()

        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return False

        duration = result.stdout.strip()

        if not duration:
            return False

        return True

    except Exception:
        return False


async def download_song(link: str) -> str:
    """
    Download audio.

    First tries the Shruti API.
    If the returned file is invalid, automatically falls back
    to yt-dlp.
    """

    video_id = get_video_id(link)

    if not video_id or len(video_id) < 3:
        return None

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    file_path = os.path.join(
        DOWNLOAD_DIR,
        f"{video_id}.mp3"
    )

    # Use existing valid file
    if (
        os.path.exists(file_path)
        and os.path.getsize(file_path) > 0
        and is_valid_media_file(file_path)
    ):
        return file_path

    # Remove broken old file
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass

    youtube_url = f"https://www.youtube.com/watch?v={video_id}"

    # ---------------------------------------------------------
    # 1. Try Shruti API
    # ---------------------------------------------------------

    if API_KEY:
        try:
            async with aiohttp.ClientSession() as session:

                async with session.get(
                    f"{API_URL}/download",
                    params={
                        "url": video_id,
                        "type": "audio",
                        "api_key": API_KEY,
                    },
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as resp:

                    if resp.status == 200:

                        with open(file_path, "wb") as f:

                            async for chunk in resp.content.iter_chunked(
                                131072
                            ):
                                if chunk:
                                    f.write(chunk)

                        # Validate API output
                        if is_valid_media_file(file_path):
                            return file_path

        except Exception:
            pass

    # Remove invalid API result
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass

    # ---------------------------------------------------------
    # 2. Fallback to yt-dlp
    # ---------------------------------------------------------

    try:

        ffmpeg_path = get_ffmpeg_path()

        output_template = os.path.join(
            DOWNLOAD_DIR,
            f"{video_id}.%(ext)s"
        )

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,

            "format": "bestaudio/best",

            "outtmpl": output_template,

            "ffmpeg_location": ffmpeg_path,

            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],

            "socket_timeout": 30,
            "retries": 3,
        }

        def run_download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([youtube_url])

        await asyncio.to_thread(run_download)

        # yt-dlp may create mp3 directly
        if (
            os.path.exists(file_path)
            and os.path.getsize(file_path) > 0
            and is_valid_media_file(file_path)
        ):
            return file_path

        # Search for another generated audio file
        for filename in os.listdir(DOWNLOAD_DIR):

            if filename.startswith(video_id):

                candidate = os.path.join(
                    DOWNLOAD_DIR,
                    filename
                )

                if is_valid_media_file(candidate):

                    if candidate != file_path:

                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)

                            os.rename(
                                candidate,
                                file_path
                            )

                        except Exception:
                            return candidate

                    return file_path

    except Exception:
        pass

    # Cleanup if everything failed
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass

    return None


async def download_video(link: str) -> str:
    """
    Download video.

    First tries the Shruti API.
    If the returned file is invalid, automatically falls back
    to yt-dlp.
    """

    video_id = get_video_id(link)

    if not video_id or len(video_id) < 3:
        return None

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    file_path = os.path.join(
        DOWNLOAD_DIR,
        f"{video_id}.mp4"
    )

    # Existing valid file
    if (
        os.path.exists(file_path)
        and os.path.getsize(file_path) > 0
        and is_valid_media_file(file_path)
    ):
        return file_path

    # Remove broken file
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass

    youtube_url = f"https://www.youtube.com/watch?v={video_id}"

    # ---------------------------------------------------------
    # 1. Try Shruti API
    # ---------------------------------------------------------

    if API_KEY:
        try:
            async with aiohttp.ClientSession() as session:

                async with session.get(
                    f"{API_URL}/download",
                    params={
                        "url": video_id,
                        "type": "video",
                        "api_key": API_KEY,
                    },
                    timeout=aiohttp.ClientTimeout(total=600),
                ) as resp:

                    if resp.status == 200:

                        with open(file_path, "wb") as f:

                            async for chunk in resp.content.iter_chunked(
                                131072
                            ):
                                if chunk:
                                    f.write(chunk)

                        if is_valid_media_file(file_path):
                            return file_path

        except Exception:
            pass

    # Remove invalid API result
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass

    # ---------------------------------------------------------
    # 2. Fallback to yt-dlp
    # ---------------------------------------------------------

    try:

        ffmpeg_path = get_ffmpeg_path()

        output_template = os.path.join(
            DOWNLOAD_DIR,
            f"{video_id}.%(ext)s"
        )

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,

            "format": "bestvideo+bestaudio/best",

            "outtmpl": output_template,

            "merge_output_format": "mp4",

            "ffmpeg_location": ffmpeg_path,

            "socket_timeout": 30,
            "retries": 3,
        }

        def run_download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([youtube_url])

        await asyncio.to_thread(run_download)

        if (
            os.path.exists(file_path)
            and os.path.getsize(file_path) > 0
            and is_valid_media_file(file_path)
        ):
            return file_path

        # Search for generated video
        for filename in os.listdir(DOWNLOAD_DIR):

            if filename.startswith(video_id):

                candidate = os.path.join(
                    DOWNLOAD_DIR,
                    filename
                )

                if is_valid_media_file(candidate):

                    if candidate != file_path:

                        try:

                            if os.path.exists(file_path):
                                os.remove(file_path)

                            os.rename(
                                candidate,
                                file_path
                            )

                        except Exception:
                            return candidate

                    return file_path

    except Exception:
        pass

    # Cleanup
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass

    return None


class YouTubeAPI:

    def __init__(self):

        self.base = "https://www.youtube.com/watch?v="

        self.regex = r"(?:youtube\.com|youtu\.be)"

        self.status = "https://www.youtube.com/oembed?url="

        self.listbase = "https://youtube.com/playlist?list="

        self.reg = re.compile(
            r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"
        )

    async def exists(
        self,
        link: str,
        videoid: Union[bool, str] = None
    ):

        if videoid:
            link = self.base + link

        return bool(
            re.search(
                self.regex,
                link
            )
        )

    async def url(
        self,
        message_1: Message
    ) -> Union[str, None]:

        messages = [message_1]

        if message_1.reply_to_message:
            messages.append(
                message_1.reply_to_message
            )

        for message in messages:

            if message.entities:

                for entity in message.entities:

                    if entity.type == MessageEntityType.URL:

                        text = (
                            message.text
                            or message.caption
                        )

                        return text[
                            entity.offset:
                            entity.offset + entity.length
                        ]

            elif message.caption_entities:

                for entity in message.caption_entities:

                    if (
                        entity.type
                        == MessageEntityType.TEXT_LINK
                    ):
                        return entity.url

        return None

    async def details(
        self,
        link: str,
        videoid: Union[bool, str] = None
    ):

        if videoid:
            link = self.base + link

        if "&" in link:
            link = link.split("&")[0]

        results = VideosSearch(
            link,
            limit=1
        )

        for result in (
            await results.next()
        )["result"]:

            title = result["title"]

            duration_min = result["duration"]

            thumbnail = (
                result["thumbnails"][0]["url"]
                .split("?")[0]
            )

            vidid = result["id"]

            duration_sec = (
                int(
                    time_to_seconds(
                        duration_min
                    )
                )
                if duration_min
                else 0
            )

        return (
            title,
            duration_min,
            duration_sec,
            thumbnail,
            vidid
        )

    async def title(
        self,
        link: str,
        videoid: Union[bool, str] = None
    ):

        if videoid:
            link = self.base + link

        if "&" in link:
            link = link.split("&")[0]

        results = VideosSearch(
            link,
            limit=1
        )

        for result in (
            await results.next()
        )["result"]:

            return result["title"]

    async def duration(
        self,
        link: str,
        videoid: Union[bool, str] = None
    ):

        if videoid:
            link = self.base + link

        if "&" in link:
            link = link.split("&")[0]

        results = VideosSearch(
            link,
            limit=1
        )

        for result in (
            await results.next()
        )["result"]:

            return result["duration"]

    async def thumbnail(
        self,
        link: str,
        videoid: Union[bool, str] = None
    ):

        if videoid:
            link = self.base + link

        if "&" in link:
            link = link.split("&")[0]

        results = VideosSearch(
            link,
            limit=1
        )

        for result in (
            await results.next()
        )["result"]:

            return (
                result["thumbnails"][0]["url"]
                .split("?")[0]
            )

    async def video(
        self,
        link: str,
        videoid: Union[bool, str] = None
    ):

        if videoid:
            link = self.base + link

        if "&" in link:
            link = link.split("&")[0]

        try:

            downloaded_file = await download_video(
                link
            )

            if downloaded_file:
                return 1, downloaded_file

            return 0, "Video download failed"

        except Exception as e:

            return 0, f"Video download error: {e}"

    async def playlist(
        self,
        link,
        limit,
        user_id,
        videoid: Union[bool, str] = None
    ):

        if videoid:
            link = self.listbase + link

        if "&" in link:
            link = link.split("&")[0]

        try:

            plist = await Playlist.get(link)

        except Exception:

            return []

        videos = plist.get("videos") or []

        ids = []

        for data in videos[:limit]:

            if not data:
                continue

            vid = data.get("id")

            if not vid:
                continue

            ids.append(vid)

        return ids

    async def track(
        self,
        link: str,
        videoid: Union[bool, str] = None
    ):

        if videoid:
            link = self.base + link

        if "&" in link:
            link = link.split("&")[0]

        results = VideosSearch(
            link,
            limit=1
        )

        for result in (
            await results.next()
        )["result"]:

            title = result["title"]

            duration_min = result["duration"]

            vidid = result["id"]

            yturl = result["link"]

            thumbnail = (
                result["thumbnails"][0]["url"]
                .split("?")[0]
            )

        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }

        return track_details, vidid

    async def formats(
        self,
        link: str,
        videoid: Union[bool, str] = None
    ):

        if videoid:
            link = self.base + link

        if "&" in link:
            link = link.split("&")[0]

        ytdl_opts = {
            "quiet": True
        }

        ydl = yt_dlp.YoutubeDL(
            ytdl_opts
        )

        with ydl:

            formats_available = []

            r = ydl.extract_info(
                link,
                download=False
            )

            for format in r["formats"]:

                try:

                    if (
                        "dash"
                        not in str(
                            format["format"]
                        ).lower()
                    ):

                        formats_available.append(
                            {
                                "format": format["format"],
                                "filesize": format.get(
                                    "filesize"
                                ),
                                "format_id": format[
                                    "format_id"
                                ],
                                "ext": format["ext"],
                                "format_note": format[
                                    "format_note"
                                ],
                                "yturl": link,
                            }
                        )

                except Exception:

                    continue

        return formats_available, link

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None
    ):

        if videoid:
            link = self.base + link

        if "&" in link:
            link = link.split("&")[0]

        a = VideosSearch(
            link,
            limit=10
        )

        result = (
            await a.next()
        ).get("result")

        title = result[query_type]["title"]

        duration_min = result[
            query_type
        ]["duration"]

        vidid = result[
            query_type
        ]["id"]

        thumbnail = (
            result[query_type]["thumbnails"][0]["url"]
            .split("?")[0]
        )

        return (
            title,
            duration_min,
            thumbnail,
            vidid
        )

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:

        if videoid:
            link = self.base + link

        try:

            if video:

                downloaded_file = await download_video(
                    link
                )

            else:

                downloaded_file = await download_song(
                    link
                )

            if downloaded_file:
                return downloaded_file, True

            return None, False

        except Exception:

            return None, False


YouTube = YouTubeAPI()

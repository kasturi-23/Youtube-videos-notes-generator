import os
import re
from http.cookiejar import MozillaCookieJar
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse, parse_qs

import requests
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api._errors import IpBlocked, RequestBlocked
from youtube_transcript_api.proxies import GenericProxyConfig, InvalidProxyConfig

SUSPECT_PATTERNS = [
    "we're sorry",
    "unusual traffic",
    "automated queries",
    "client does not have permission",
    "captcha",
]

DEFAULT_USER_AGENT = os.environ.get(
    "YOUTUBE_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/118.0.0.0 Safari/537.36",
)
COOKIE_ENV_VARS = ("YOUTUBE_COOKIES_FILE", "YT_COOKIES_FILE")


def format_duration(seconds: Optional[int]) -> Optional[str]:
    if seconds is None:
        return None
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return None
    if seconds < 0:
        return None
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def is_valid_youtube_url(url):
    # Regex to validate YouTube URL
    youtube_regex = r'^(https?://)?(www\.)?(youtube\.com|youtu\.?be)/.+$'
    return re.match(youtube_regex, url) is not None


def is_suspect_content(text: str) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in SUSPECT_PATTERNS)

RATE_LIMIT_ERROR = "Error: YouTube rate-limited the caption request. Please wait and try again."
IP_BLOCKED_ERROR = (
    "Error: YouTube blocked transcript access for this IP. Provide a proxy or browser cookies and try again."
)


def resolve_cookie_path() -> Optional[str]:
    for env_var in COOKIE_ENV_VARS:
        configured = os.environ.get(env_var)
        if not configured:
            continue
        expanded = os.path.expanduser(configured)
        if os.path.exists(expanded):
            return expanded
        print(f"Cookie file specified in {env_var} not found: {expanded}")
    return None


def build_proxy_settings() -> Tuple[Dict[str, str], Optional[GenericProxyConfig]]:
    http_proxy = os.environ.get("YOUTUBE_PROXY_HTTP") or os.environ.get("YOUTUBE_PROXY")
    https_proxy = os.environ.get("YOUTUBE_PROXY_HTTPS") or os.environ.get("YOUTUBE_PROXY")
    if not http_proxy and not https_proxy:
        return {}, None
    try:
        proxy_config = GenericProxyConfig(http_url=http_proxy, https_url=https_proxy)
        proxy_dict = {
            "http": http_proxy or https_proxy,
            "https": https_proxy or http_proxy,
        }
        return proxy_dict, proxy_config
    except InvalidProxyConfig as e:
        print(f"Invalid proxy configuration: {e}")
        return {}, None


def create_http_session(proxy_dict: Dict[str, str], cookies_path: Optional[str]) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": DEFAULT_USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})

    if proxy_dict:
        session.proxies.update(proxy_dict)

    if cookies_path:
        try:
            cookie_jar = MozillaCookieJar()
            cookie_jar.load(cookies_path, ignore_discard=True, ignore_expires=True)
            session.cookies = cookie_jar
            print(f"Loaded cookies from {cookies_path}")
        except Exception as e:
            print(f"Failed to load cookies from {cookies_path}: {e}")

    return session


def update_metadata_from_info(info: Dict, metadata: Dict[str, Optional[str]]) -> None:
    if not info:
        return
    metadata["url"] = metadata.get("url") or info.get("webpage_url") or info.get("original_url")
    title = info.get("title")
    if title and not metadata.get("title"):
        metadata["title"] = title
    channel = info.get("uploader") or info.get("channel")
    if channel and not metadata.get("channel"):
        metadata["channel"] = channel
    duration = info.get("duration")
    if duration is not None:
        metadata["duration_seconds"] = duration
        if not metadata.get("duration"):
            metadata["duration"] = format_duration(duration)


def fetch_video_metadata(
    video_url: str,
    session: requests.Session,
    cookies_path: Optional[str],
    proxy_dict: Dict[str, str],
) -> Optional[Dict]:
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'extract_flat': False,
        'http_headers': {
            'User-Agent': DEFAULT_USER_AGENT,
            'Accept-Language': 'en-US,en;q=0.9',
        },
    }
    if cookies_path:
        ydl_opts['cookiefile'] = cookies_path
    if proxy_dict:
        ydl_opts['proxy'] = proxy_dict.get('https') or proxy_dict.get('http')

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            return ydl.extract_info(video_url, download=False)
        except Exception as e:
            print(f"Failed to fetch video metadata via yt-dlp: {e}")
            return None


def get_transcript(video_url):
    """
    Retrieves the transcript for a given YouTube video URL.
    """
    metadata = {
        "title": None,
        "channel": None,
        "duration": None,
        "duration_seconds": None,
        "url": video_url,
    }

    if not is_valid_youtube_url(video_url):
        print(f"Invalid YouTube URL: {video_url}")
        return "Error: Invalid YouTube URL", metadata

    cookies_path = resolve_cookie_path()
    proxy_dict, proxy_config = build_proxy_settings()
    session = create_http_session(proxy_dict, cookies_path)

    rate_limited = False
    ip_blocked = False

    try:
        try:
            print("Step: Attempting to fetch transcript via yt-dlp auto-captions")
            transcript_text, rate_limited = get_transcript_via_yt_dlp(
                video_url, session, cookies_path, proxy_dict, metadata
            )
            if transcript_text and transcript_text.strip():
                if is_suspect_content(transcript_text):
                    print("Transcript appears to be an error page; ignoring yt-dlp result.")
                else:
                    print("Transcript fetched via yt-dlp auto-captions")
                    return transcript_text.strip(), metadata
        except Exception as e:
            print(f"yt-dlp auto-captions error: {e}. Will try other methods.")

        try:
            video_id = extract_video_id(video_url)
            if video_id:
                print("Step: Attempting to fetch transcript via YouTube Transcript API")
                transcript_text = fetch_transcript_via_api(video_id, proxy_config, session)
                if transcript_text:
                    if is_suspect_content(transcript_text):
                        print("YouTube Transcript API returned suspicious content; ignoring.")
                    else:
                        print("Transcript fetched from YouTube Transcript API")
                        if metadata.get("title") is None:
                            info = fetch_video_metadata(video_url, session, cookies_path, proxy_dict)
                            if info:
                                update_metadata_from_info(info, metadata)
                        return transcript_text.strip(), metadata
        except (TranscriptsDisabled, NoTranscriptFound) as e:
            print(f"YouTube Transcript API unavailable for this video: {e}.")
        except IpBlocked:
            print("YouTube Transcript API reports IP blocked.")
            ip_blocked = True
        except RequestBlocked:
            print("YouTube Transcript API reports request blocked (possible consent screen).")
            ip_blocked = True
        except Exception as e:
            print(f"YouTube Transcript API error: {e}.")

        if rate_limited:
            if metadata.get("title") is None:
                info = fetch_video_metadata(video_url, session, cookies_path, proxy_dict)
                if info:
                    update_metadata_from_info(info, metadata)
            return RATE_LIMIT_ERROR, metadata
        if ip_blocked:
            if metadata.get("title") is None:
                info = fetch_video_metadata(video_url, session, cookies_path, proxy_dict)
                if info:
                    update_metadata_from_info(info, metadata)
            return IP_BLOCKED_ERROR, metadata

        if metadata.get("title") is None:
            info = fetch_video_metadata(video_url, session, cookies_path, proxy_dict)
            if info:
                update_metadata_from_info(info, metadata)

        return "Error: No captions available for this video", metadata
    finally:
        session.close()


def extract_video_id(url: str) -> str:
    """Extracts the YouTube video ID from a URL."""
    try:
        parsed = urlparse(url)
        if parsed.hostname in ("youtu.be",):
            return parsed.path.lstrip('/')
        if parsed.hostname and 'youtube' in parsed.hostname:
            query = parse_qs(parsed.query)
            if 'v' in query:
                return query['v'][0]
            # handle /embed/VIDEO_ID or /v/VIDEO_ID
            parts = parsed.path.split('/')
            for i, part in enumerate(parts):
                if part in ("embed", "v") and i + 1 < len(parts):
                    return parts[i + 1]
        return ""
    except Exception:
        return ""


def get_transcript_via_yt_dlp(
    video_url: str,
    session: requests.Session,
    cookies_path: Optional[str],
    proxy_dict: Dict[str, str],
    metadata: Dict[str, Optional[str]],
) -> Tuple[str, bool]:
    """Fetch auto-generated captions via yt-dlp and return (text, rate_limited flag)."""
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en', 'en-US', 'en-GB'],
        'subtitlesformat': 'vtt',
        'extract_flat': False,
        'http_headers': {
            'User-Agent': DEFAULT_USER_AGENT,
            'Accept-Language': 'en-US,en;q=0.9',
        },
    }
    if cookies_path:
        ydl_opts['cookiefile'] = cookies_path
    if proxy_dict:
        ydl_opts['proxy'] = proxy_dict.get('https') or proxy_dict.get('http')

    rate_limited = False
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = None
        try:
            info = ydl.extract_info(video_url, download=False)
            print(f"Video title: {info.get('title', 'Unknown')}")
            update_metadata_from_info(info, metadata)
            
            # Try automatic captions first
            auto_captions = info.get('automatic_captions', {})
            print(f"Auto captions available: {list(auto_captions.keys())}")
            
            for lang in ['en', 'en-US', 'en-GB']:
                if lang in auto_captions:
                    for track in auto_captions[lang]:
                        if track.get('ext') in ['vtt', 'srv1', 'srv2', 'srv3']:
                            url = track.get('url')
                            if not url:
                                continue
                            try:
                                print(f"Trying auto-caption URL: {url[:100]}...")
                                response = session.get(url, timeout=15)
                                response.raise_for_status()
                                text = response.text
                                if not text or text.startswith('#EXTM3U'):
                                    continue
                                cleaned = vtt_to_text(text)
                                if cleaned and not is_suspect_content(cleaned):
                                    return cleaned, rate_limited
                                print("Auto-caption content looked invalid; trying next track.")
                            except requests.HTTPError as e:
                                if e.response is not None and e.response.status_code == 429:
                                    rate_limited = True
                                    print("Received 429 while fetching auto-captions; stopping attempts.")
                                    return "", rate_limited
                                print(f"HTTP error fetching auto-caption: {e}")
                                continue
                            except Exception as e:
                                print(f"Error fetching auto-caption: {e}")
                                continue
            
            # Try manual subtitles if auto-captions failed
            subtitles = info.get('subtitles', {})
            print(f"Manual subtitles available: {list(subtitles.keys())}")
            
            for lang in ['en', 'en-US', 'en-GB']:
                if lang in subtitles:
                    for track in subtitles[lang]:
                        if track.get('ext') in ['vtt', 'srv1', 'srv2', 'srv3']:
                            url = track.get('url')
                            if not url:
                                continue
                            try:
                                print(f"Trying subtitle URL: {url[:100]}...")
                                response = session.get(url, timeout=15)
                                response.raise_for_status()
                                text = response.text
                                if not text or text.startswith('#EXTM3U'):
                                    continue
                                cleaned = vtt_to_text(text)
                                if cleaned and not is_suspect_content(cleaned):
                                    return cleaned, rate_limited
                                print("Subtitle content looked invalid; trying next track.")
                            except requests.HTTPError as e:
                                if e.response is not None and e.response.status_code == 429:
                                    rate_limited = True
                                    print("Received 429 while fetching subtitles; stopping attempts.")
                                    return "", rate_limited
                                print(f"HTTP error fetching subtitle: {e}")
                                continue
                            except Exception as e:
                                print(f"Error fetching subtitle: {e}")
                                continue
        except Exception as e:
            print(f"Error extracting video info: {e}")
    return "", rate_limited


def vtt_to_text(vtt: str) -> str:
    lines = []
    for line in vtt.splitlines():
        line = re.sub(r'<[^>]+>', '', line).strip()
        if not line:
            continue
        if line.startswith('WEBVTT'):
            continue
        if '-->' in line:
            continue
        if re.match(r'^\d+$', line):
            continue
        lines.append(line)
    return " ".join(lines)


def fetch_transcript_via_api(
    video_id: str,
    proxy_config: Optional[GenericProxyConfig],
    session: requests.Session,
) -> str:
    """Fetch transcript text using youtube_transcript_api with backward compatibility."""

    def build_api_instance() -> Optional[YouTubeTranscriptApi]:
        params = {}
        if proxy_config is not None:
            params["proxy_config"] = proxy_config
        if session is not None:
            params["http_client"] = session
        try:
            return YouTubeTranscriptApi(**params)
        except TypeError:
            # Older versions may not accept http_client
            params.pop("http_client", None)
            try:
                return YouTubeTranscriptApi(**params)
            except Exception as e:
                print(f"Failed to initialize YouTubeTranscriptApi with provided params: {e}")
        except Exception as e:
            print(f"Failed to initialize YouTubeTranscriptApi: {e}")
        return None

    api_instance = build_api_instance()

    if api_instance is not None:
        fetch_method = getattr(api_instance, "fetch", None)
        if callable(fetch_method):
            entries = fetch_method(video_id, languages=('en',))
            return " ".join(chunk.get('text', '') for chunk in entries).strip()

        list_method = getattr(api_instance, "list", None)
        if callable(list_method):
            print("Using YouTubeTranscriptApi.list fallback to retrieve transcript.")
            transcripts = list_method(video_id)
            transcript = transcripts.find_transcript(['en'])
            entries = transcript.fetch()
            return " ".join(chunk.get('text', '') for chunk in entries).strip()

    # Older versions exposed module-level functions
    get_method = getattr(YouTubeTranscriptApi, "get_transcript", None)
    if callable(get_method):
        transcript = get_method(video_id, languages=['en'])
        return " ".join(chunk.get('text', '') for chunk in transcript).strip()

    list_method = getattr(YouTubeTranscriptApi, "list_transcripts", None)
    if callable(list_method):
        print("youtube_transcript_api.get_transcript unavailable; using list_transcripts fallback.")
        transcripts = list_method(video_id)
        transcript = transcripts.find_transcript(['en'])
        entries = transcript.fetch()
        return " ".join(chunk.get('text', '') for chunk in entries).strip()

    print("youtube_transcript_api lacks supported transcript retrieval methods; cannot fetch.")
    return ""

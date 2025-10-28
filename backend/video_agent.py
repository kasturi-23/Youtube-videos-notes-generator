import os
import re
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import yt_dlp
import requests

def is_valid_youtube_url(url):
    # Regex to validate YouTube URL
    youtube_regex = r'^(https?://)?(www\.)?(youtube\.com|youtu\.?be)/.+$'
    return re.match(youtube_regex, url) is not None

def get_transcript(video_url):
    """
    Retrieves the transcript for a given YouTube video URL.
    """
    # Try to fetch transcript via YouTube Transcript API first
    # Try yt-dlp automatic captions
    try:
        print("Step: Attempting to fetch transcript via yt-dlp auto-captions")
        transcript_text = get_transcript_via_yt_dlp(video_url)
        if transcript_text and transcript_text.strip():
            print("Transcript fetched via yt-dlp auto-captions")
            return transcript_text.strip()
    except Exception as e:
        print(f"yt-dlp auto-captions error: {e}. Will try other methods.")

    try:
        video_id = extract_video_id(video_url)
        if video_id:
            print("Step: Attempting to fetch transcript via YouTube Transcript API")
            transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = transcripts.find_transcript(['en']).fetch()
            transcript_text = " ".join([chunk['text'] for chunk in transcript])
            if transcript_text.strip():
                print("Transcript fetched from YouTube Transcript API")
                return transcript_text.strip()
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        print(f"YouTube Transcript API unavailable for this video: {e}.")
    except Exception as e:
        print(f"YouTube Transcript API error: {e}.")

    if not is_valid_youtube_url(video_url):
        print(f"Invalid YouTube URL: {video_url}")
        return "Error: Invalid YouTube URL"

    # Do not attempt audio download + STT; return a clear error instead
    return "Error: No captions available for this video"
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

def get_transcript_via_yt_dlp(video_url: str) -> str:
    """Fetch auto-generated captions via yt-dlp and return plain text."""
    ydl_opts = { 
        'skip_download': True, 
        'quiet': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en', 'en-US', 'en-GB'],
        'subtitlesformat': 'vtt',
        'extract_flat': False
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(video_url, download=False)
            print(f"Video title: {info.get('title', 'Unknown')}")
            
            # Try automatic captions first
            auto_captions = info.get('automatic_captions', {})
            print(f"Auto captions available: {list(auto_captions.keys())}")
            
            for lang in ['en', 'en-US', 'en-GB']:
                if lang in auto_captions:
                    for track in auto_captions[lang]:
                        if track.get('ext') in ['vtt', 'srv1', 'srv2', 'srv3']:
                            url = track.get('url')
                            if url:
                                try:
                                    print(f"Trying auto-caption URL: {url[:100]}...")
                                    text = requests.get(url, timeout=15).text
                                    if text and not text.startswith('#EXTM3U'):
                                        return vtt_to_text(text)
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
                            if url:
                                try:
                                    print(f"Trying subtitle URL: {url[:100]}...")
                                    text = requests.get(url, timeout=15).text
                                    if text and not text.startswith('#EXTM3U'):
                                        return vtt_to_text(text)
                                except Exception as e:
                                    print(f"Error fetching subtitle: {e}")
                                    continue
        except Exception as e:
            print(f"Error extracting video info: {e}")
    return ""

def vtt_to_text(vtt: str) -> str:
    lines = []
    for line in vtt.splitlines():
        line = line.strip()
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


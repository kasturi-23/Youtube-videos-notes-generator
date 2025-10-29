from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Startup Diagnostics ---
print("--- Backend Server Starting ---")
google_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
gemini_key = os.environ.get("GOOGLE_API_KEY")

if google_creds and "PASTE_YOUR" not in google_creds and os.path.exists(google_creds):
    print("[OK] Google Application Credentials path is valid.")
elif google_creds and "PASTE_YOUR" in google_creds:
    print("[ERROR] Please open the .env file and replace the placeholder with your credentials path.")
else:
    print("[ERROR] GOOGLE_APPLICATION_CREDENTIALS is not set or the file path is invalid.")
    
if gemini_key and "PASTE_YOUR" not in gemini_key:
    print("[OK] Google API Key (Gemini) is set.")
elif gemini_key and "PASTE_YOUR" in gemini_key:
    print("[ERROR] Please open the .env file and replace the placeholder with your Gemini API key.")
else:
    print("[ERROR] GOOGLE_API_KEY is not set.")
print("-----------------------------")
# -------------------------

# Import agent modules
import video_agent
import text_agent
import summarizer_agent

app = Flask(__name__)
# ... (rest of the file is unchanged)
CORS(app)


def is_transcript_error(transcript):
    """Return True when the transcript is an error string."""
    if not isinstance(transcript, str):
        return False
    return transcript.strip().lower().startswith("error:")


def extract_transcript_metadata(video_url, result):
    if isinstance(result, tuple) and len(result) == 2:
        transcript, metadata = result
    else:
        transcript = result
        metadata = {}

    metadata = metadata or {}
    metadata.setdefault('title', None)
    metadata.setdefault('channel', None)
    metadata.setdefault('duration', None)
    metadata.setdefault('duration_seconds', None)
    metadata.setdefault('url', video_url)

    return transcript, metadata


@app.route('/api/process-video', methods=['POST'])
def process_video():
    data = request.get_json()
    video_url = data.get('video_url')

    if not video_url:
        return jsonify({'error': 'Video URL is required'}), 400

    # 1. Video_Agent: Get transcript (and metadata)
    transcript_result = video_agent.get_transcript(video_url)
    transcript, metadata = extract_transcript_metadata(video_url, transcript_result)
    if not transcript or is_transcript_error(transcript):
        if is_transcript_error(transcript):
            error_message = transcript.strip()
            if error_message in (video_agent.RATE_LIMIT_ERROR, video_agent.IP_BLOCKED_ERROR):
                status_code = 429
            else:
                status_code = 500
        else:
            error_message = 'Failed to retrieve transcript. Check backend logs for details.'
            status_code = 500
        return jsonify({'error': error_message, 'metadata': metadata}), status_code

    # 2. Text_Agent: Clean transcript
    cleaned_transcript = text_agent.clean_transcript(transcript)

    # 3. Summarizer_Agent: Generate notes
    video_title = metadata.get('title')
    if not video_title:
        try:
            from pytube import YouTube
            yt = YouTube(video_url)
            video_title = yt.title
            metadata['title'] = metadata.get('title') or yt.title
            metadata['channel'] = metadata.get('channel') or getattr(yt, 'author', None)
            metadata['duration'] = metadata.get('duration') or video_agent.format_duration(getattr(yt, 'length', None))
            metadata['url'] = metadata.get('url') or getattr(yt, 'watch_url', video_url)
        except Exception:
            video_title = "Unknown Video"

    metadata['title'] = metadata.get('title') or video_title

    notes_json_string = summarizer_agent.summarize_transcript(cleaned_transcript, metadata)
    if not notes_json_string:
        return jsonify({'error': 'Failed to generate notes from summarizer agent.'}), 500
        
    # Clean the string to make it valid JSON
    notes_json_string = notes_json_string.strip().replace('```json', '').replace('```', '')

    try:
        notes = json.loads(notes_json_string)
    except json.JSONDecodeError:
        return jsonify({'error': 'Failed to parse summary from AI. The response was not valid JSON.'}), 500

    # Check if the parsed notes contain an error from the agent
    if isinstance(notes, dict):
        if 'error' in notes:
            return jsonify({'error': notes['error']}), 500
        notes_metadata = notes.get('metadata')
        if isinstance(notes_metadata, dict):
            for key in ('title', 'channel', 'duration', 'duration_seconds', 'url'):
                value = notes_metadata.get(key)
                if value:
                    metadata[key] = value

    return jsonify({
        'transcript': cleaned_transcript,
        'notes': notes,
        'metadata': metadata
    })

@app.route('/api/process-batch', methods=['POST'])
def process_batch():
    data = request.get_json()
    video_urls = data.get('video_urls', [])
    
    if not video_urls or not isinstance(video_urls, list):
        return jsonify({'error': 'Video URLs list is required'}), 400
    
    if len(video_urls) > 10:  # Limit batch size
        return jsonify({'error': 'Maximum 10 videos per batch'}), 400
    
    results = []
    errors = []
    
    for i, video_url in enumerate(video_urls):
        try:
            print(f"Processing video {i+1}/{len(video_urls)}: {video_url}")

            transcript_result = video_agent.get_transcript(video_url)
            transcript, metadata = extract_transcript_metadata(video_url, transcript_result)
            if not transcript or is_transcript_error(transcript):
                error_message = (
                    transcript.strip()
                    if is_transcript_error(transcript)
                    else 'Failed to retrieve transcript'
                )
                errors.append({'video_url': video_url, 'error': error_message, 'metadata': metadata})
                if error_message in (video_agent.RATE_LIMIT_ERROR, video_agent.IP_BLOCKED_ERROR):
                    break
                continue

            cleaned_transcript = text_agent.clean_transcript(transcript)

            video_title = metadata.get('title')
            if not video_title:
                try:
                    from pytube import YouTube
                    yt = YouTube(video_url)
                    video_title = yt.title
                    metadata['title'] = metadata.get('title') or yt.title
                    metadata['channel'] = metadata.get('channel') or getattr(yt, 'author', None)
                    metadata['duration'] = metadata.get('duration') or video_agent.format_duration(getattr(yt, 'length', None))
                    metadata['url'] = metadata.get('url') or getattr(yt, 'watch_url', video_url)
                except Exception:
                    video_title = f"Video {i+1}"

            metadata['title'] = metadata.get('title') or video_title

            metadata['title'] = metadata.get('title') or video_title
            notes_json_string = summarizer_agent.summarize_transcript(cleaned_transcript, metadata)
            if not notes_json_string:
                errors.append({'video_url': video_url, 'error': 'Failed to generate notes', 'metadata': metadata})
                continue

            notes_json_string = notes_json_string.strip().replace('```json', '').replace('```', '')

            try:
                notes = json.loads(notes_json_string)
                if isinstance(notes, dict):
                    if 'error' in notes:
                        errors.append({'video_url': video_url, 'error': notes['error'], 'metadata': metadata})
                        continue
                    notes_metadata = notes.get('metadata')
                    if isinstance(notes_metadata, dict):
                        for key in ('title', 'channel', 'duration', 'duration_seconds', 'url'):
                            value = notes_metadata.get(key)
                            if value:
                                metadata[key] = value

                video_title = metadata.get('title') or video_title

                results.append({
                    'video_url': video_url,
                    'video_title': video_title,
                    'transcript': cleaned_transcript,
                    'notes': notes,
                    'metadata': metadata
                })

            except json.JSONDecodeError:
                errors.append({'video_url': video_url, 'error': 'Failed to parse AI response', 'metadata': metadata})
                continue

        except Exception as e:
            errors.append({'video_url': video_url, 'error': str(e)})
            continue
    
    return jsonify({
        'results': results,
        'errors': errors,
        'summary': {
            'total': len(video_urls),
            'successful': len(results),
            'failed': len(errors)
        }
    })

@app.route('/api/process-playlist', methods=['POST'])
def process_playlist():
    data = request.get_json()
    playlist_url = data.get('playlist_url')
    
    if not playlist_url:
        return jsonify({'error': 'Playlist URL is required'}), 400
    
    try:
        import yt_dlp
        
        # Extract video URLs from playlist
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            playlist_info = ydl.extract_info(playlist_url, download=False)
            
        if not playlist_info or 'entries' not in playlist_info:
            return jsonify({'error': 'Failed to extract playlist information'}), 500
            
        video_urls = []
        for entry in playlist_info['entries']:
            if entry and 'url' in entry:
                video_urls.append(entry['url'])
        
        if not video_urls:
            return jsonify({'error': 'No videos found in playlist'}), 500
            
        # Limit playlist size
        if len(video_urls) > 20:
            video_urls = video_urls[:20]
            return jsonify({'error': f'Playlist too large. Processing first 20 videos out of {len(playlist_info["entries"])}'}), 400
        
        # Process videos in batch
        results = []
        errors = []
        
        for i, video_url in enumerate(video_urls):
            try:
                print(f"Processing playlist video {i+1}/{len(video_urls)}: {video_url}")

                transcript_result = video_agent.get_transcript(video_url)
                transcript, metadata = extract_transcript_metadata(video_url, transcript_result)
                if not transcript or is_transcript_error(transcript):
                    error_message = (
                        transcript.strip()
                        if is_transcript_error(transcript)
                        else 'Failed to retrieve transcript'
                    )
                    errors.append({'video_url': video_url, 'error': error_message, 'metadata': metadata})
                    if error_message in (video_agent.RATE_LIMIT_ERROR, video_agent.IP_BLOCKED_ERROR):
                        break
                    continue

                cleaned_transcript = text_agent.clean_transcript(transcript)

                video_title = metadata.get('title')
                if not video_title:
                    try:
                        from pytube import YouTube
                        yt = YouTube(video_url)
                        video_title = yt.title
                        metadata['title'] = metadata.get('title') or yt.title
                        metadata['channel'] = metadata.get('channel') or getattr(yt, 'author', None)
                        metadata['duration'] = metadata.get('duration') or video_agent.format_duration(getattr(yt, 'length', None))
                        metadata['url'] = metadata.get('url') or getattr(yt, 'watch_url', video_url)
                    except Exception:
                        video_title = f"Playlist Video {i+1}"

                metadata['title'] = metadata.get('title') or video_title

                notes_json_string = summarizer_agent.summarize_transcript(cleaned_transcript, metadata)
                if not notes_json_string:
                    errors.append({'video_url': video_url, 'error': 'Failed to generate notes', 'metadata': metadata})
                    continue

                notes_json_string = notes_json_string.strip().replace('```json', '').replace('```', '')

                try:
                    notes = json.loads(notes_json_string)
                    if isinstance(notes, dict):
                        if 'error' in notes:
                            errors.append({'video_url': video_url, 'error': notes['error'], 'metadata': metadata})
                            continue
                        notes_metadata = notes.get('metadata')
                        if isinstance(notes_metadata, dict):
                            for key in ('title', 'channel', 'duration', 'duration_seconds', 'url'):
                                value = notes_metadata.get(key)
                                if value:
                                    metadata[key] = value

                    video_title = metadata.get('title') or video_title

                    results.append({
                        'video_url': video_url,
                        'video_title': video_title,
                        'transcript': cleaned_transcript,
                        'notes': notes,
                        'metadata': metadata
                    })

                except json.JSONDecodeError:
                    errors.append({'video_url': video_url, 'error': 'Failed to parse AI response', 'metadata': metadata})
                    continue

            except Exception as e:
                errors.append({'video_url': video_url, 'error': str(e)})
                continue
        
        return jsonify({
            'playlist_url': playlist_url,
            'playlist_title': playlist_info.get('title', 'Unknown Playlist'),
            'results': results,
            'errors': errors,
            'summary': {
                'total': len(video_urls),
                'successful': len(results),
                'failed': len(errors)
            }
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to process playlist: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)

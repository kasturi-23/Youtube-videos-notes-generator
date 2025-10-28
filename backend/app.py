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

@app.route('/api/process-video', methods=['POST'])
def process_video():
    data = request.get_json()
    video_url = data.get('video_url')

    if not video_url:
        return jsonify({'error': 'Video URL is required'}), 400

    # 1. Video_Agent: Get transcript
    transcript = video_agent.get_transcript(video_url)
    if not transcript:
        return jsonify({'error': 'Failed to retrieve transcript. Check backend logs for details.'}), 500

    # 2. Text_Agent: Clean transcript
    cleaned_transcript = text_agent.clean_transcript(transcript)

    # 3. Summarizer_Agent: Generate notes
    try:
        from pytube import YouTube
        yt = YouTube(video_url)
        video_title = yt.title
    except Exception:
        video_title = "Unknown Video"

    notes_json_string = summarizer_agent.summarize_transcript(cleaned_transcript, video_title)
    if not notes_json_string:
        return jsonify({'error': 'Failed to generate notes from summarizer agent.'}), 500
        
    # Clean the string to make it valid JSON
    notes_json_string = notes_json_string.strip().replace('```json', '').replace('```', '')

    try:
        notes = json.loads(notes_json_string)
    except json.JSONDecodeError:
        return jsonify({'error': 'Failed to parse summary from AI. The response was not valid JSON.'}), 500

    # Check if the parsed notes contain an error from the agent
    if isinstance(notes, dict) and 'error' in notes:
        return jsonify({'error': notes['error']}), 500

    return jsonify({
        'transcript': cleaned_transcript,
        'notes': notes
    })

if __name__ == '__main__':
    app.run(debug=True)

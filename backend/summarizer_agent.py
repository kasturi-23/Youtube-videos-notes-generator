import google.generativeai as genai
import os

def summarize_transcript(transcript, video_title=""):
    """
    Generates structured lecture notes from a transcript using the Gemini API.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return '{"error": "GOOGLE_API_KEY environment variable not set."}'
    
    genai.configure(api_key=api_key)

    candidate_models = [
        'models/gemini-2.5-flash',
        'gemini-2.5-flash',
        'models/gemini-1.5-flash',
        'models/gemini-1.5-flash-latest',
        'models/gemini-1.5-pro',
        'models/gemini-pro',
        'gemini-pro'
    ]

    prompt = f"""
    You are Summarizer_Agent. Use the Google Gemini API to summarize transcripts.
    Input: A clean transcript of a video lecture.
    Output: Structured lecture notes in JSON format including:
    1.  "title": The title of the video. If no title is provided, create a suitable one.
    2.  "key_topics": A list of key topics covered.
    3.  "main_ideas": A paragraph summarizing the main ideas.
    4.  "notes": A list of bullet-point notes.
    5.  "summary": A concise summary paragraph of the entire lecture.
    6.  "quiz": A list of 5 quiz-style comprehension questions based on the content.

    Here is the transcript:
    ---
    {transcript}
    ---
    Video Title: "{video_title}"
    """

    last_error = None
    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            last_error = e
            print(f"Error in Summarizer_Agent with {model_name}: {e}")
            continue
    return f'{{"error": "Error from Gemini API: {str(last_error)}"}}'

import json
import os

import google.generativeai as genai


def summarize_transcript(transcript, metadata=None):
    """
    Generates detailed lecture notes from a transcript using the Gemini API.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return '{"error": "GOOGLE_API_KEY environment variable not set."}'

    genai.configure(api_key=api_key)

    metadata = metadata or {}
    metadata_json = json.dumps(metadata)

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
    You are Summarizer_Agent. Convert the transcript into a comprehensive study report.

    REQUIREMENTS:
    - Output valid JSON only, no extra commentary.
    - Preserve provided metadata exactly when present; do not guess unknown values. Use null when uncertain.
    - Provide rich, detailed content grounded in the transcript. Avoid hallucinations.

    JSON SCHEMA (all fields required):
    {{
      "metadata": {{
        "title": string or null,
        "channel": string or null,
        "duration": string or null,
        "url": string or null
      }},
      "overview": string (2-3 sentences capturing the lecture focus),
      "sections": [
        {{
          "time": string or null (MM:SS or HH:MM:SS),
          "topic": string,
          "summary": string (3-4 sentences with key ideas for this segment)
        }},
        ... 5-7 sections spanning the lecture
      ],
      "notes": [
        string bullet points highlighting important concepts (minimum 8 items)
      ],
      "key_takeaways": [
        concise insights learners should remember (5-7 items)
      ],
      "references": [
        {{
          "title": string,
          "url": string or null
        }},
        ... include 3-5 credible resources relevant to the topic; use null for missing URLs
      ],
      "quiz_questions": [
        {{
          "question": string,
          "options": [
            "A. ...",
            "B. ...",
            "C. ...",
            "D. ..."
          ],
          "answer": string that exactly matches one option
        }},
        ... include 5 comprehension questions
      ],
      "next_steps": [
        string suggestions for further study or practice (3-4 items)
      ]
    }}

    PROVIDED METADATA:
    {metadata_json}

    TRANSCRIPT:
    \"\"\"{transcript}\"\"\"
    """

    last_error = None
    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            if response.text:
                return response.text
            last_error = ValueError("Empty response from Gemini")
        except Exception as e:
            last_error = e
            print(f"Error in Summarizer_Agent with {model_name}: {e}")
            continue
    return f'{{"error": "Error from Gemini API: {str(last_error)}"}}'

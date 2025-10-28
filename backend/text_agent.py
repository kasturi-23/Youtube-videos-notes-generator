import re

def clean_transcript(transcript):
    """
    Cleans and preprocesses the transcript.
    """
    # Remove timestamps and other noise
    transcript = re.sub(r'\[.*?\]', '', transcript)
    transcript = re.sub(r'\(.*?\)', '', transcript)

    # Fix punctuation and sentence casing
    transcript = transcript.strip()
    sentences = re.split('(?<=[.!?]) +', transcript)
    cleaned_sentences = [s.capitalize() for s in sentences]
    
    return " ".join(cleaned_sentences)

# YouTube Video Lecture Notes Generator

A full-stack web application that automatically generates structured, AI-powered notes from YouTube videos. Extract transcripts, clean text, and create comprehensive summaries with sections, key takeaways, quiz questions, and more using Google's Gemini AI.

## Features

- **Single Video Processing**: Generate detailed notes from individual YouTube videos
- **Batch Processing**: Process multiple videos simultaneously (up to 10 videos)
- **Playlist Processing**: Extract and process entire YouTube playlists (up to 20 videos)
- **AI-Powered Summarization**: Uses Google Gemini AI to create structured notes including:
  - Video overview and metadata
  - Section-by-section breakdowns with timestamps
  - Detailed notes and key takeaways
  - Quiz questions for learning reinforcement
  - References and next steps
- **Modern Web Interface**: Clean, responsive React frontend with tabbed interface
- **RESTful API**: Flask-based backend with CORS support for easy integration

## Prerequisites

Before running this application, make sure you have the following installed:

- Python 3.8 or higher
- Node.js 14 or higher
- npm or yarn
- Google Cloud Platform account with:
  - Google Cloud Speech-to-Text API enabled
  - Google Generative AI (Gemini) API access
  - Service account credentials (JSON key file)

## Installation

### Backend Setup

1. **Clone the repository and navigate to the backend directory:**
   ```bash
   git clone <repository-url>
   cd video-lecture-notes/backend
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   Create a `.env` file in the backend directory with the following variables:
   ```
   GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account-key.json
   GOOGLE_API_KEY=your-gemini-api-key
   ```

   Replace the placeholders with your actual:
   - Path to your Google Cloud service account JSON key file
   - Google Gemini API key

### Frontend Setup

1. **Navigate to the frontend directory:**
   ```bash
   cd ../frontend
   ```

2. **Install Node.js dependencies:**
   ```bash
   npm install
   ```

## Usage

### Running the Application

1. **Start the backend server:**
   ```bash
   cd backend
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   python app.py
   ```
   The backend will run on `http://127.0.0.1:5000`

2. **Start the frontend (in a new terminal):**
   ```bash
   cd frontend
   npm start
   ```
   The frontend will run on `http://localhost:3000`

3. **Open your browser and navigate to `http://localhost:3000`**

### Using the Application

- **Single Video**: Enter a YouTube URL and click "Generate Notes"
- **Batch Processing**: Enter multiple YouTube URLs (one per line, max 10) and click "Process Batch"
- **Playlist Processing**: Enter a YouTube playlist URL and click "Process Playlist"

The application will extract the video transcript, clean the text, and generate structured notes using AI.

## API Endpoints

The backend provides the following REST API endpoints:

### POST `/api/process-video`
Process a single YouTube video.
- **Request Body**: `{"video_url": "https://www.youtube.com/watch?v=..."}`
- **Response**: JSON with transcript, notes, and metadata

### POST `/api/process-batch`
Process multiple YouTube videos.
- **Request Body**: `{"video_urls": ["url1", "url2", ...]}`
- **Response**: JSON array with results and errors

### POST `/api/process-playlist`
Process an entire YouTube playlist.
- **Request Body**: `{"playlist_url": "https://www.youtube.com/playlist?list=..."}`
- **Response**: JSON with playlist info and processed videos

## Project Structure

```
video-lecture-notes/
├── backend/
│   ├── app.py                 # Main Flask application
│   ├── video_agent.py         # YouTube transcript extraction
│   ├── text_agent.py          # Text cleaning and processing
│   ├── summarizer_agent.py    # AI summarization with Gemini
│   ├── requirements.txt       # Python dependencies
│   └── .env                   # Environment variables (create this)
├── frontend/
│   ├── src/
│   │   ├── App.js             # Main React component
│   │   └── ...                # Other React components
│   ├── package.json           # Node.js dependencies
│   └── public/                # Static assets
└── README.md                  # This file
```

## Troubleshooting

### Common Issues

1. **Google API Credentials Error**:
   - Ensure your `.env` file has the correct paths and keys
   - Verify your Google Cloud project has the required APIs enabled
   - Check that your service account has appropriate permissions

2. **Transcript Extraction Fails**:
   - Some videos may not have transcripts available
   - Check for rate limiting or IP blocking from YouTube

3. **AI Summarization Errors**:
   - Verify your Gemini API key is valid and has quota remaining
   - Check the backend logs for detailed error messages

### Rate Limits and Quotas

- YouTube Transcript API: May have rate limits for frequent requests
- Google Gemini API: Check your quota limits in Google Cloud Console
- Batch processing: Limited to 10 videos, playlist processing to 20 videos

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and test thoroughly
4. Commit your changes: `git commit -am 'Add new feature'`
5. Push to the branch: `git push origin feature-name`
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Google Cloud Platform for Speech-to-Text and Generative AI APIs
- YouTube Transcript API for transcript extraction
- React and Flask communities for excellent frameworks


# Whisper Transcription

A web application for YouTube video transcription using OpenAI Whisper and MLX-Whisper for Apple Silicon. This project provides a simple web interface to transcribe YouTube videos and download SRT subtitle files.

## Features

- 🎵 YouTube video transcription to SRT format
- 🌐 Web-based interface for easy use
- 📱 Responsive design
- 🔄 Cross-platform compatibility
- ⚡ Automatic model selection (MLX-Whisper for Apple Silicon, OpenAI Whisper for others)
- 📥 Direct SRT file download

## Requirements

- Python 3.8+
- FFmpeg (for audio processing)
- **Apple Silicon Macs**: MLX-Whisper for optimal performance
- **Other platforms**: OpenAI Whisper with CUDA/CPU support

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/MinjaeKim09/whisperYTtoSRT.git
   cd whisperYTtoSRT
   ```
2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Install FFmpeg:**
   - **macOS:** `brew install ffmpeg`
   - **Ubuntu/Debian:** `sudo apt install ffmpeg`
   - **Windows:** Download from [FFmpeg website](https://ffmpeg.org/download.html)

## Usage

1. **Start the application:**
   ```bash
   python app.py
   ```
2. **Open your browser and navigate to:**
   ```
   http://localhost:8080
   ```
3. **Enter a YouTube URL and select your preferred model size.**
4. **Click "Start Transcription" and wait for processing to complete.**
5. **Download the generated SRT file.**

## How It Works

1. **Audio Extraction**: Downloads audio from the provided YouTube URL using yt-dlp
2. **Transcription**: Processes the entire audio file using Whisper (batch processing)
3. **SRT Generation**: Converts the transcription into standard SRT subtitle format
4. **Download**: Provides the SRT file for download

## Model Sizes

- **Tiny**: Fastest processing, less accurate
- **Base**: Good balance of speed and accuracy
- **Small**: Better accuracy than base
- **Medium**: Recommended balance (default)
- **Large**: Best accuracy, slower processing

## Project Structure

```
whisperYTtoSRT/
├── app.py              # FastAPI web application
├── transcriber.py      # Core transcription logic
├── templates/          # HTML templates
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Technical Details

- Uses **MLX-Whisper** on Apple Silicon for optimal performance
- Falls back to **OpenAI Whisper** on other platforms
- Subprocess isolation ensures proper memory cleanup after transcription
- Temporary files are automatically cleaned up

## License

MIT License - see LICENSE file for details. 
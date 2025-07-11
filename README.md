# whisperRealtime

A web application for real-time speech-to-text transcription using OpenAI Whisper (and MLX-Whisper for Apple Silicon). This project is a real-time extension of whisperWebUI, designed to provide live transcription as audio is received, rather than processing pre-recorded files or YouTube videos.

## Features

- 🎤 Real-time audio transcription in the browser
- ⚡ Live transcription feed updates in the UI as you speak
- 🌐 Web-based interface for easy use
- 🔄 Cross-platform compatibility

## Requirements

- Python 3.8+
- FFmpeg (for audio processing)
- Microphone access in browser
- **Apple Silicon Macs**: MLX-Whisper for optimal performance
- **Other platforms**: OpenAI Whisper with CUDA/CPU support

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/MinjaeKim09/whisperRealtime.git
   cd whisperRealtime
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
3. **Allow microphone access and start speaking.**
4. **See real-time transcription appear in the UI.**

## Roadmap: Real-Time Transcription Feed

To implement a real-time transcription feed in the UI, the following steps are planned:

1. **WebSocket Integration:**
   - Use WebSockets (e.g., Flask-SocketIO) to enable real-time, bidirectional communication between the server and browser.
2. **Frontend Audio Capture:**
   - Use JavaScript (Web Audio API/MediaRecorder) to capture microphone audio in the browser and stream it to the backend in small chunks.
3. **Backend Streaming Transcription:**
   - Modify the backend to accept audio streams and transcribe them incrementally using Whisper.
   - Send partial transcription results back to the frontend as they are produced.
4. **Live UI Updates:**
   - Update the frontend to display the transcription feed in real time, appending new text as it arrives.
5. **Performance Optimization:**
   - Tune chunk sizes, buffering, and latency for smooth, low-lag transcription.
6. **(Optional) Speaker Diarization & Language Support:**
   - Add features like speaker identification or multi-language support if needed.

## Project Structure

```
whisperRealtime/
├── app.py              # Flask web application (to be updated for real-time)
├── transcriber.py      # Core transcription logic (to be updated for streaming)
├── templates/          # HTML templates (to be updated for live feed)
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## License

MIT License - see LICENSE file for details. 
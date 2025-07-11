# YTtoSRT

A web application that transcribes YouTube videos to SRT subtitle files using unified Whisper implementation with auto-detection.

## Features

- 🎥 Download audio from YouTube videos
- 🎤 Auto-detect and use the best Whisper implementation (MLX for Apple Silicon, OpenAI Whisper as fallback)
- 📝 Generate SRT subtitle files with timestamps
- 🌐 Web-based interface for easy use
- ⚡ Real-time processing and download
- 🔄 Cross-platform compatibility

## Requirements

- Python 3.8+
- FFmpeg (for audio processing)
- Internet connection for YouTube downloads
- **Apple Silicon Macs**: MLX-Whisper for optimal performance
- **Other platforms**: OpenAI Whisper with CUDA/CPU support

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/YTtoSRT.git
   cd YTtoSRT
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

3. **Enter a YouTube URL and click "Generate SRT"**

4. **Download the generated SRT file**

## API Usage

You can also use the API directly:

```bash
curl -X POST http://localhost:8080/generate-srt \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=VIDEO_ID"}'
```

## Project Structure

```
YTtoSRT/
├── app.py              # Flask web application
├── transcriber.py      # Core transcription logic with auto-detection
├── templates/          # HTML templates
│   └── index_basic.html
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## How It Works

1. **YouTube Download:** Uses `yt-dlp` to download audio from YouTube videos
2. **Audio Processing:** Converts audio to WAV format using FFmpeg
3. **Auto-Detection:** Automatically detects the best available Whisper implementation:
   - **MLX-Whisper** (Apple Silicon optimized) - preferred on M1/M2/M3 Macs
   - **OpenAI Whisper** (CUDA/CPU compatible) - fallback for other platforms
4. **Transcription:** Uses the detected implementation with medium model for accuracy
5. **SRT Generation:** Creates properly formatted SRT subtitle files with timestamps
6. **Cleanup:** Automatically removes temporary files after processing

## Whisper Implementation Auto-Detection

The application automatically chooses the best Whisper implementation:

### **Apple Silicon Macs (M1/M2/M3):**
- **Primary:** MLX-Whisper (optimized for Apple Neural Engine)
- **Benefits:** Faster processing, lower memory usage, native optimization

### **Other Platforms (Intel Macs, Windows, Linux):**
- **Fallback:** OpenAI Whisper with CUDA/CPU support
- **Benefits:** Wide compatibility, GPU acceleration when available

### **Manual Override:**
You can force a specific implementation by setting environment variables:
```bash
# Force MLX-Whisper
export WHISPER_TYPE=mlx

# Force OpenAI Whisper
export WHISPER_TYPE=openai
```

## Dependencies

- `flask` - Web framework
- `mlx-whisper` - MLX-optimized Whisper for Apple Silicon
- `openai-whisper` - Standard Whisper for other platforms
- `yt-dlp` - YouTube downloader
- `mlx` - Apple's MLX framework for machine learning
- `torch` - PyTorch for OpenAI Whisper

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Troubleshooting

- **FFmpeg not found:** Make sure FFmpeg is installed and in your PATH
- **Memory issues:** The medium model provides good balance of speed and accuracy
- **Download errors:** Check if the YouTube URL is valid and publicly accessible
- **Whisper not found:** Install either `mlx-whisper` or `openai-whisper`
- **Platform-specific issues:** The app auto-detects the best implementation for your system

## Acknowledgments

- OpenAI for the original Whisper model
- Apple for the MLX framework
- MLX-Whisper developers for Apple Silicon optimization
- yt-dlp developers for YouTube downloading capabilities
- Flask team for the web framework 
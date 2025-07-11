# transcriber.py
import os
import yt_dlp
import sys
import uuid # Used for unique filenames
import json
import argparse
import asyncio
from typing import Generator, Dict, Any

def get_whisper_implementation():
    """
    Auto-detect and return the best available Whisper implementation.
    Returns: 'mlx', 'openai', or 'none'
    """
    # Check for manual override via environment variable
    forced_type = os.getenv("WHISPER_TYPE", "").lower()
    if forced_type in ["mlx", "openai"]:
        return forced_type
    
    # Try MLX-Whisper first (optimized for Apple Silicon)
    try:
        import mlx_whisper
        return "mlx"
    except ImportError:
        pass
    
    # Fallback to OpenAI Whisper
    try:
        import whisper
        return "openai"
    except ImportError:
        pass
    
    return "none"

def format_timestamp(seconds):
    """Converts seconds into the SRT timestamp format (HH:MM:SS,ms)."""
    seconds = float(seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

def transcribe_with_mlx(audio_path, model_size="medium"):
    """Transcribe audio using MLX-Whisper (Apple Silicon optimized)."""
    import mlx_whisper
    print(f"INFO: Using MLX-Whisper ({model_size} model)...", file=sys.stderr)
    return mlx_whisper.transcribe(audio_path, path_or_hf_repo=f"mlx-community/whisper-{model_size}")

def transcribe_with_openai(audio_path, model_size="medium"):
    """Transcribe audio using OpenAI Whisper (CUDA/CPU compatible)."""
    import whisper
    print(f"INFO: Using OpenAI Whisper ({model_size} model)...", file=sys.stderr)
    model = whisper.load_model(model_size)
    return model.transcribe(audio_path, fp16=False)  # fp16=False for CPU compatibility

def stream_transcribe_with_mlx(audio_path, model_size="medium") -> Generator[Dict[str, Any], None, None]:
    """Stream transcription using MLX-Whisper, yielding segments as they're processed."""
    import mlx_whisper
    print(f"INFO: Using MLX-Whisper ({model_size} model) for streaming...", file=sys.stderr)
    
    # Start transcription
    yield {"type": "status", "message": "Starting transcription with MLX-Whisper..."}
    
    # MLX-Whisper doesn't have built-in streaming, so we'll transcribe and yield segments
    result = mlx_whisper.transcribe(audio_path, path_or_hf_repo=f"mlx-community/whisper-{model_size}")
    
    # Yield each segment as it becomes available
    for i, segment in enumerate(result['segments']):
        start_time = format_timestamp(segment['start'])  # type: ignore
        end_time = format_timestamp(segment['end'])  # type: ignore
        text = segment['text'].strip()  # type: ignore
        
        segment_data = {
            "type": "segment",
            "index": i + 1,
            "start_time": start_time,
            "end_time": end_time,
            "text": text,
            "srt_format": f"{i + 1}\n{start_time} --> {end_time}\n{text}\n"
        }
        yield segment_data

def stream_transcribe_with_openai(audio_path, model_size="medium") -> Generator[Dict[str, Any], None, None]:
    """Stream transcription using OpenAI Whisper, yielding segments as they're processed."""
    import whisper
    print(f"INFO: Using OpenAI Whisper ({model_size} model) for streaming...", file=sys.stderr)
    
    # Start transcription
    yield {"type": "status", "message": "Starting transcription with OpenAI Whisper..."}
    
    model = whisper.load_model(model_size)
    result = model.transcribe(audio_path, fp16=False)
    
    # Yield each segment as it becomes available
    for i, segment in enumerate(result['segments']):
        start_time = format_timestamp(segment['start'])  # type: ignore
        end_time = format_timestamp(segment['end'])  # type: ignore
        text = segment['text'].strip()  # type: ignore
        
        segment_data = {
            "type": "segment",
            "index": i + 1,
            "start_time": start_time,
            "end_time": end_time,
            "text": text,
            "srt_format": f"{i + 1}\n{start_time} --> {end_time}\n{text}\n"
        }
        yield segment_data

def process_youtube_video_streaming(url: str, model_size: str = "medium") -> Generator[Dict[str, Any], None, None]:
    """
    Stream processing of YouTube video: downloads audio, transcribes it, and yields progress updates.
    Yields dictionaries with different types: 'status', 'segment', 'complete', 'error'
    """
    # Use a unique ID for filenames to avoid conflicts
    request_id = str(uuid.uuid4())
    
    # Define paths for temporary files
    temp_dir = os.path.join(os.getcwd(), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
    output_filename_base = f'audio_{request_id}'
    output_path_template = os.path.join(temp_dir, f'{output_filename_base}.%(ext)s')
    final_wav_path = os.path.join(temp_dir, f'{output_filename_base}.wav')

    try:
        # Step 1: Download audio
        yield {"type": "status", "message": "Downloading audio from YouTube..."}
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }],
            'outtmpl': output_path_template,
            'quiet': True,
            'noplaylist': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        if not os.path.exists(final_wav_path):
            raise FileNotFoundError(f"Expected audio file not found at {final_wav_path}")
        
        yield {"type": "status", "message": "Audio download complete. Starting transcription..."}

        # Step 2: Stream transcription
        implementation = get_whisper_implementation()
        
        if implementation == "mlx":
            transcription_generator = stream_transcribe_with_mlx(final_wav_path, model_size)
        elif implementation == "openai":
            transcription_generator = stream_transcribe_with_openai(final_wav_path, model_size)
        else:
            yield {"type": "error", "message": "No Whisper implementation found. Please install mlx-whisper or openai-whisper."}
            return

        # Collect all segments for final SRT
        all_segments = []
        
        # Yield each segment as it's processed
        for segment_data in transcription_generator:
            if segment_data["type"] == "segment":
                all_segments.append(segment_data["srt_format"])
            yield segment_data

        # Step 3: Complete transcription
        full_srt_content = "\n".join(all_segments)
        yield {
            "type": "complete",
            "message": "Transcription complete!",
            "srt_content": full_srt_content,
            "total_segments": len(all_segments)
        }

    except yt_dlp.utils.DownloadError as e:
        yield {"type": "error", "message": f"Error downloading the video: {e}"}
    except Exception as e:
        yield {"type": "error", "message": f"An unexpected error occurred: {e}"}
    finally:
        # Clean up the downloaded WAV file
        if os.path.exists(final_wav_path):
            try:
                os.remove(final_wav_path)
                print(f"INFO: Removed temporary file '{final_wav_path}'.", file=sys.stderr)
            except OSError as e:
                print(f"ERROR: Could not remove file {final_wav_path}: {e}", file=sys.stderr)

def process_youtube_video(url, model_size="medium"):
    """
    Downloads audio from a YouTube URL, transcribes it, and returns the SRT content.
    Returns a tuple: (success, message_or_srt_content)
    """
    # Use a unique ID for filenames to avoid conflicts if multiple users use the app
    request_id = str(uuid.uuid4())
    
    # --- Define paths for temporary files ---
    # It's good practice to use a dedicated 'temp' folder
    temp_dir = os.path.join(os.getcwd(), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
    output_filename_base = f'audio_{request_id}'
    output_path_template = os.path.join(temp_dir, f'{output_filename_base}.%(ext)s')
    final_wav_path = os.path.join(temp_dir, f'{output_filename_base}.wav')

    try:
        # --- Step 1: Set up yt-dlp options for WAV extraction ---
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }],
            'outtmpl': output_path_template,
            'quiet': True,
            'noplaylist': True,
        }

        # --- Step 2: Download and convert the audio ---
        print(f"INFO: Downloading audio for URL: {url}", file=sys.stderr)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        if not os.path.exists(final_wav_path):
             raise FileNotFoundError(f"Expected audio file not found at {final_wav_path}")
        print(f"INFO: Audio saved to '{final_wav_path}'", file=sys.stderr)

        # --- Step 3: Auto-detect and use the best Whisper implementation ---
        implementation = get_whisper_implementation()
        
        if implementation == "mlx":
            result = transcribe_with_mlx(final_wav_path, model_size)
        elif implementation == "openai":
            result = transcribe_with_openai(final_wav_path, model_size)
        else:
            return (False, "No Whisper implementation found. Please install mlx-whisper or openai-whisper.")

        # --- Step 4: Generate SRT content in memory ---
        srt_content = []
        for i, segment in enumerate(result['segments']):
            start_time = format_timestamp(segment['start'])  # type: ignore
            end_time = format_timestamp(segment['end'])  # type: ignore
            text = segment['text'].strip()  # type: ignore
            
            srt_content.append(f"{i + 1}")
            srt_content.append(f"{start_time} --> {end_time}")
            srt_content.append(f"{text}\n")

        print("INFO: Transcription complete.", file=sys.stderr)
        
        return (True, "\n".join(srt_content))

    except yt_dlp.utils.DownloadError as e:
        print(f"ERROR: Download failed: {e}", file=sys.stderr)
        return (False, "Error downloading the video. Please check if the URL is correct and public.")
    except Exception as e:
        print(f"ERROR: An unexpected error occurred: {e}", file=sys.stderr)
        return (False, f"An internal error occurred: {e}")
    finally:
        # --- Step 5: Clean up the downloaded WAV file ---
        if os.path.exists(final_wav_path):
            try:
                os.remove(final_wav_path)
                print(f"INFO: Removed temporary file '{final_wav_path}'.", file=sys.stderr)
            except OSError as e:
                print(f"ERROR: Could not remove file {final_wav_path}: {e}", file=sys.stderr)

def standalone_transcribe(url, model_size="medium"):
    """
    Standalone function that can be run as a separate process.
    Returns JSON result that can be parsed by the main process.
    """
    # Capture all stdout to prevent interference with JSON output
    import io
    import contextlib
    import sys
    
    # Create a string buffer to capture stdout
    stdout_buffer = io.StringIO()
    
    try:
        # Redirect stdout to our buffer during transcription
        with contextlib.redirect_stdout(stdout_buffer):
            success, result = process_youtube_video(url, model_size)
        
        # Return JSON result
        output = {
            "success": success,
            "result": result if success else result,  # result is either SRT content or error message
            "error": None if success else result
        }
        
        # Print JSON to stdout (this is what the Flask app will capture)
        print(json.dumps(output))
        return 0 if success else 1
        
    except Exception as e:
        error_output = {
            "success": False,
            "result": None,
            "error": str(e)
        }
        print(json.dumps(error_output))
        return 1

if __name__ == "__main__":
    # Command line interface for standalone execution
    parser = argparse.ArgumentParser(description="Transcribe YouTube video to SRT")
    parser.add_argument("--url", help="YouTube URL to transcribe")
    parser.add_argument("--model-size", default="medium", choices=["tiny", "base", "small", "medium", "large"], 
                       help="Whisper model size (default: medium)")
    parser.add_argument("--stream", action="store_true", help="Enable streaming mode for real-time updates")
    
    args = parser.parse_args()
    
    # Check if we have a URL (either positional or named argument)
    url = args.url
    if not url and len(sys.argv) > 1 and not sys.argv[1].startswith('--'):
        # Handle positional URL argument for backwards compatibility
        url = sys.argv[1]
    
    if not url:
        print(json.dumps({
            "success": False,
            "error": "URL is required"
        }))
        sys.exit(1)
    
    if args.stream:
        # Streaming mode for WebSocket
        for update in process_youtube_video_streaming(url, args.model_size):
            print(json.dumps(update))
            sys.stdout.flush()  # Ensure immediate output
        sys.exit(0)
    else:
        # Traditional mode for HTTP endpoint
        exit_code = standalone_transcribe(url, args.model_size)
        sys.exit(exit_code)


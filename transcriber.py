# transcriber.py
import os
import yt_dlp
import sys
import uuid # Used for unique filenames
import json
import argparse
import subprocess
import math
import time

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
    """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"

def get_audio_duration(audio_path):
    """Get the duration of an audio file using ffprobe."""
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
            '-of', 'csv=p=0', audio_path
        ], capture_output=True, text=True)
        return float(result.stdout.strip())
    except:
        return None

def split_audio_into_chunks(audio_path, chunk_duration=30):
    """Split audio file into chunks for real-time processing."""
    chunks = []
    temp_dir = os.path.dirname(audio_path)
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    
    # Get audio duration
    duration = get_audio_duration(audio_path)
    if duration is None:
        raise Exception("Could not determine audio duration")
    
    # Calculate number of chunks
    num_chunks = math.ceil(duration / chunk_duration)
    
    for i in range(num_chunks):
        start_time = i * chunk_duration
        chunk_path = os.path.join(temp_dir, f"{base_name}_chunk_{i:03d}.wav")
        
        # Use ffmpeg to extract chunk
        cmd = [
            'ffmpeg', '-i', audio_path, '-ss', str(start_time), 
            '-t', str(chunk_duration), '-c', 'copy', chunk_path, '-y', '-loglevel', 'quiet'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            chunks.append({
                'path': chunk_path,
                'start_time': start_time,
                'end_time': min(start_time + chunk_duration, duration),
                'chunk_index': i
            })
        else:
            print(f"WARNING: Failed to create chunk {i}: {result.stderr}", file=sys.stderr)
    
    return chunks

def transcribe_with_mlx(audio_path, model_size="medium"):
    """Transcribe audio using MLX-Whisper (Apple Silicon optimized)."""
    import mlx_whisper
    return mlx_whisper.transcribe(audio_path, path_or_hf_repo=f"mlx-community/whisper-{model_size}")

def transcribe_with_openai(audio_path, model_size="medium", model=None):
    """Transcribe audio using OpenAI Whisper (CUDA/CPU compatible)."""
    import whisper
    if model is None:
        model = whisper.load_model(model_size)
    return model.transcribe(audio_path, fp16=False)

def process_youtube_video_streaming(url, model_size="medium"):
    """
    Downloads audio from a YouTube URL and transcribes it with real-time chunk processing.
    Provides immediate feedback by processing chunks as soon as they're ready.
    """
    # Use a unique ID for filenames to avoid conflicts
    request_id = str(uuid.uuid4())
    
    # Define paths for temporary files
    temp_dir = os.path.join(os.getcwd(), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
    output_filename_base = f'audio_{request_id}'
    output_path_template = os.path.join(temp_dir, f'{output_filename_base}.%(ext)s')
    final_wav_path = os.path.join(temp_dir, f'{output_filename_base}.wav')
    
    chunks_to_cleanup = []
    
    try:
        # Step 1: Download audio
        print(json.dumps({
            'status': 'downloading',
            'message': 'Downloading audio from YouTube...',
            'progress': 5
        }))
        
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
        
        # Step 2: Split into chunks for real-time processing
        print(json.dumps({
            'status': 'preparing',
            'message': 'Splitting audio for real-time processing...',
            'progress': 10
        }))
        
        chunks = split_audio_into_chunks(final_wav_path, chunk_duration=30)
        chunks_to_cleanup = [chunk['path'] for chunk in chunks]
        
        total_chunks = len(chunks)
        print(json.dumps({
            'status': 'ready',
            'message': f'Ready to process {total_chunks} chunks',
            'total_chunks': total_chunks,
            'progress': 15
        }))
        
        # Step 3: Load Whisper model once
        implementation = get_whisper_implementation()
        if implementation == "none":
            raise Exception("No Whisper implementation found")
        
        print(json.dumps({
            'status': 'loading_model',
            'message': f'Loading {implementation} Whisper model ({model_size})...',
            'progress': 20
        }))
        
        # Pre-load model for OpenAI Whisper to avoid reloading
        model = None
        if implementation == "openai":
            import whisper
            model = whisper.load_model(model_size)
        
        # Step 4: Process each chunk in real-time
        all_segments = []
        segment_counter = 1
        
        for i, chunk in enumerate(chunks):
            chunk_progress = 20 + (i / total_chunks) * 70  # 20-90% range
            
            print(json.dumps({
                'status': 'processing_chunk',
                'message': f'Transcribing chunk {i+1}/{total_chunks} ({chunk["start_time"]:.1f}s - {chunk["end_time"]:.1f}s)',
                'chunk_index': i,
                'current_chunk': i + 1,
                'total_chunks': total_chunks,
                'chunk_start': chunk['start_time'],
                'chunk_end': chunk['end_time'],
                'progress': chunk_progress
            }))
            
            try:
                # Transcribe this chunk immediately
                if implementation == "mlx":
                    result = transcribe_with_mlx(chunk['path'], model_size)
                else:
                    result = transcribe_with_openai(chunk['path'], model_size, model)
                
                # Process segments from this chunk
                chunk_segments = []
                segments = result.get('segments', [])
                for segment in segments:
                    if isinstance(segment, dict):
                        # Adjust timestamps to account for chunk offset
                        adjusted_start = segment.get('start', 0) + chunk['start_time']
                        adjusted_end = segment.get('end', 0) + chunk['start_time']
                        
                        start_time = format_timestamp(adjusted_start)
                        end_time = format_timestamp(adjusted_end)
                        text = segment.get('text', '').strip()
                        
                        if text:  # Only add non-empty segments
                            srt_entry = f"{segment_counter}\n{start_time} --> {end_time}\n{text}\n"
                            chunk_segments.append(srt_entry)
                            all_segments.append(srt_entry)
                            segment_counter += 1
                            
                            # Stream individual segment completion
                            print(json.dumps({
                                'status': 'segment_completed',
                                'segment_index': segment_counter - 2,
                                'segment_start': adjusted_start,
                                'segment_end': adjusted_end,
                                'segment_text': text,
                                'chunk_index': i,
                                'current_chunk': i + 1,
                                'total_chunks': total_chunks,
                                'partial_srt': '\n'.join(all_segments),
                                'progress': chunk_progress + (len(chunk_segments) / max(len(segments), 1)) * (70 / total_chunks)
                            }))
                
                # Send chunk completion update
                chunk_text = result.get('text', '')
                if isinstance(chunk_text, str):
                    chunk_text = chunk_text.strip()
                else:
                    chunk_text = str(chunk_text).strip()
                print(json.dumps({
                    'status': 'chunk_completed',
                    'message': f'Completed chunk {i+1}/{total_chunks}',
                    'chunk_index': i,
                    'chunk_text': chunk_text,
                    'segments_in_chunk': len(chunk_segments),
                    'progress': 20 + ((i + 1) / total_chunks) * 70
                }))
                
            except Exception as e:
                print(json.dumps({
                    'status': 'chunk_error',
                    'message': f'Error processing chunk {i+1}: {str(e)}',
                    'chunk_index': i,
                    'error': str(e)
                }))
        
        # Step 5: Final result
        final_srt = '\n'.join(all_segments)
        print(json.dumps({
            'status': 'completed',
            'message': 'Transcription completed successfully!',
            'progress': 100,
            'final_srt': final_srt,
            'total_segments': len(all_segments)
        }))
        
        return True
        
    except Exception as e:
        print(json.dumps({
            'status': 'error',
            'error': str(e),
            'message': f'Transcription failed: {str(e)}'
        }))
        return False
        
    finally:
        # Cleanup temporary files
        files_to_cleanup = [final_wav_path] + chunks_to_cleanup
        for file_path in files_to_cleanup:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"INFO: Removed temporary file '{file_path}'.", file=sys.stderr)
                except OSError as e:
                    print(f"ERROR: Could not remove file {file_path}: {e}", file=sys.stderr)

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
    parser.add_argument("--streaming", action="store_true", help="Process with real-time chunk streaming")
    
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
    
    # Process transcription
    if args.streaming:
        # Real-time streaming processing
        success = process_youtube_video_streaming(url, args.model_size)
        sys.exit(0 if success else 1)
    else:
        # Original single-file processing
        exit_code = standalone_transcribe(url, args.model_size)
        sys.exit(exit_code)


# app.py
import os
import sys
import json
import subprocess
import asyncio
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request

app = FastAPI()

# Mount templates - use absolute path relative to this script
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

class TranscriptionRequest(BaseModel):
    url: str
    model_size: str = "medium"

@app.get("/")
async def index(request: Request):
    """Serve the main page."""
    return templates.TemplateResponse("index.html", {"request": request})

# --- Original API Route (keeping for backwards compatibility) ---
@app.post('/generate-srt')
async def generate_srt(request: TranscriptionRequest):
    """
    Receives a YouTube URL, spawns a separate process for transcription,
    and returns the SRT file.
    """
    url = request.url
    
    if not url:
        raise HTTPException(status_code=400, detail="URL is required.")

    try:
        # Check if transcriber.py exists
        transcriber_path = os.path.join(os.path.dirname(__file__), 'transcriber.py')
        if not os.path.exists(transcriber_path):
            raise HTTPException(status_code=500, detail=f"transcriber.py not found at {transcriber_path}")
        
        print(f"DEBUG: Running transcriber with URL: {url}", file=sys.stderr)
        print(f"DEBUG: Transcriber path: {transcriber_path}", file=sys.stderr)
        print(f"DEBUG: Model size: {request.model_size}", file=sys.stderr)
        
        # Prepare the command
        command = [
            sys.executable,  # Use the same Python interpreter
            transcriber_path,  # Run the transcriber script with full path
            '--url', url,  # Pass the URL with --url flag
            '--model-size', request.model_size  # Use selected model size
        ]
        
        print(f"DEBUG: Executing command: {' '.join(command)}", file=sys.stderr)
        
        # Spawn a separate Python process for transcription
        # This ensures the model is completely unloaded when the process exits
        result = subprocess.run(command, 
        capture_output=True,  # Capture output
        text=True,  # Return text instead of bytes
        timeout=300,  # 5 minute timeout
        cwd=os.path.dirname(__file__)  # Set working directory to app's directory
        )
        
        # Check if the process completed successfully
        if result.returncode != 0:
            # Try to parse error from stderr
            error_msg = result.stderr.strip() if result.stderr else "Transcription failed"
            # Log detailed error information
            print(f"ERROR: Process failed with return code {result.returncode}", file=sys.stderr)
            print(f"ERROR: stderr: {repr(result.stderr)}", file=sys.stderr)
            print(f"ERROR: stdout: {repr(result.stdout)}", file=sys.stderr)
            raise HTTPException(status_code=500, detail=error_msg)
        
        # Parse the JSON output from the transcription process
        try:
            # Clean the output - remove any leading/trailing whitespace
            stdout_clean = result.stdout.strip()
            
            # Debug: log what we're trying to parse
            print(f"DEBUG: Raw stdout: {repr(stdout_clean)}", file=sys.stderr)
            
            if not stdout_clean:
                raise HTTPException(status_code=500, detail="No output from transcription process")
            
            output_data = json.loads(stdout_clean)
            
            if not output_data.get('success', False):
                error_msg = output_data.get('error', 'Transcription failed')
                raise HTTPException(status_code=500, detail=error_msg)
            
            # Get the SRT content
            srt_content = output_data.get('result', '')
            
            if not srt_content:
                raise HTTPException(status_code=500, detail="No transcription content generated")
            
            # Create a response that the browser will treat as a file download
            return Response(
                content=srt_content,
                media_type="text/plain",
                headers={"Content-Disposition": "attachment; filename=transcription.srt"}
            )
            
        except json.JSONDecodeError as e:
            # Log the problematic output for debugging
            print(f"ERROR: Failed to parse JSON. Raw output: {repr(result.stdout)}", file=sys.stderr)
            print(f"ERROR: stderr output: {repr(result.stderr)}", file=sys.stderr)
            raise HTTPException(status_code=500, detail=f"Failed to parse transcription output: {e}. Check server logs for details.")
            
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Transcription timed out after 5 minutes")
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Transcription process failed: {e}")
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

# --- New Streaming API Route ---
@app.post('/generate-srt-stream')
async def generate_srt_stream(request: TranscriptionRequest):
    """
    Receives a YouTube URL and streams transcription progress in real-time.
    Returns Server-Sent Events with chunked transcription results.
    """
    url = request.url
    
    if not url:
        raise HTTPException(status_code=400, detail="URL is required.")

    async def event_stream():
        try:
            # Check if transcriber.py exists
            transcriber_path = os.path.join(os.path.dirname(__file__), 'transcriber.py')
            if not os.path.exists(transcriber_path):
                yield f"data: {json.dumps({'error': f'transcriber.py not found at {transcriber_path}'})}\n\n"
                return
            
            yield f"data: {json.dumps({'status': 'starting', 'message': 'Initializing transcription...'})}\n\n"
            
            # Prepare the command for streaming processing
            command = [
                sys.executable,
                transcriber_path,
                '--url', url,
                '--model-size', request.model_size,
                '--streaming'  # New flag for segment-based streaming
            ]
            
            print(f"DEBUG: Executing chunked command: {' '.join(command)}", file=sys.stderr)
            
            # Start the subprocess
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.path.dirname(__file__)
            )
            
            # Read output line by line
            if process.stdout:
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    
                    try:
                        # Parse each line as JSON
                        line_str = line.decode().strip()
                        if line_str:
                            # Validate JSON before sending
                            data = json.loads(line_str)
                            yield f"data: {line_str}\n\n"
                    except json.JSONDecodeError:
                        # Skip non-JSON lines (debug output)
                        continue
            
            # Wait for process to complete
            await process.wait()
            
            if process.returncode != 0:
                stderr_output = b""
                if process.stderr:
                    stderr_output = await process.stderr.read()
                error_msg = stderr_output.decode().strip() if stderr_output else "Transcription failed"
                yield f"data: {json.dumps({'error': error_msg})}\n\n"
            else:
                yield f"data: {json.dumps({'status': 'completed', 'message': 'Transcription completed successfully!'})}\n\n"
                
        except Exception as e:
            print(f"ERROR: Streaming error: {e}", file=sys.stderr)
            yield f"data: {json.dumps({'error': f'An unexpected error occurred: {e}'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

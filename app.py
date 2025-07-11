# app.py
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import subprocess
import json
import os
import sys
import uvicorn

# Initialize the FastAPI app
app = FastAPI(title="WhisperRealtime", description="Real-time speech-to-text transcription")

# Set up templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Pydantic model for request validation
class TranscriptionRequest(BaseModel):
    url: str

# --- Route to serve the main HTML page ---
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Renders the main user interface page with real-time preview."""
    return templates.TemplateResponse("index.html", {"request": request})

# --- API Route to handle the transcription process ---
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
        
        # Spawn a separate Python process for transcription
        # This ensures the model is completely unloaded when the process exits
        result = subprocess.run([
            sys.executable,  # Use the same Python interpreter
            transcriber_path,  # Run the transcriber script with full path
            url,  # Pass the URL as argument
            '--model-size', 'medium'  # Use medium model size
        ], 
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
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

# --- WebSocket endpoint for real-time transcription ---
@app.websocket("/ws/transcribe")
async def websocket_transcribe(websocket: WebSocket):
    """
    WebSocket endpoint for real-time transcription.
    Handles streaming transcription of YouTube videos with real-time updates.
    Uses subprocess to ensure proper memory cleanup.
    """
    await websocket.accept()
    try:
        while True:
            # Wait for transcription request from client
            data = await websocket.receive_text()
            
            try:
                request_data = json.loads(data)
                url = request_data.get('url')
                model_size = request_data.get('model_size', 'medium')
                
                if not url:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "URL is required"
                    }))
                    continue
                
                # Check if transcriber.py exists
                transcriber_path = os.path.join(os.path.dirname(__file__), 'transcriber.py')
                if not os.path.exists(transcriber_path):
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": f"transcriber.py not found at {transcriber_path}"
                    }))
                    continue
                
                # Send initial status
                await websocket.send_text(json.dumps({
                    "type": "status",
                    "message": "Starting transcription process..."
                }))
                
                # Spawn a separate Python process for transcription with streaming output
                # This ensures the model is completely unloaded when the process exits
                process = subprocess.Popen([
                    sys.executable,  # Use the same Python interpreter
                    transcriber_path,  # Run the transcriber script with full path
                    '--stream',  # Enable streaming mode
                    '--url', url,  # Pass the URL as argument
                    '--model-size', model_size  # Use specified model size
                ], 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.path.dirname(__file__)  # Set working directory to app's directory
                )
                
                # Stream output from the subprocess
                while True:
                    # Read a line from stdout
                    line = process.stdout.readline() if process.stdout else None
                    if not line and process.poll() is not None:
                        break
                    
                    if line:
                        try:
                            # Parse the JSON update from the subprocess
                            update = json.loads(line.strip())
                            # Send the update to the client
                            await websocket.send_text(json.dumps(update))
                            
                            # Break if there's an error to prevent further processing
                            if update.get("type") == "error":
                                break
                                
                        except json.JSONDecodeError:
                            # If it's not JSON, it might be a debug message
                            print(f"DEBUG from subprocess: {line.strip()}", file=sys.stderr)
                
                # Wait for the process to complete
                return_code = process.wait()
                
                if return_code != 0:
                    # Read any error output
                    stderr_output = process.stderr.read() if process.stderr else ""
                    error_msg = stderr_output.strip() if stderr_output else "Transcription process failed"
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": error_msg
                    }))
                
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format"
                }))
            except Exception as e:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"An unexpected error occurred: {str(e)}"
                }))
            
    except WebSocketDisconnect:
        print("Client disconnected from WebSocket")
    except Exception as e:
        print(f"WebSocket error: {e}", file=sys.stderr)

# --- Health check endpoint ---
@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "whisperRealtime"}

# --- Main entry point for running the app ---
if __name__ == '__main__':
    # Use uvicorn to run the FastAPI app
    uvicorn.run("app:app", host='0.0.0.0', port=8080, reload=True)

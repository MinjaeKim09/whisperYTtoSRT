# app.py
import os
import sys
import json
import subprocess
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request

app = FastAPI()

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

class TranscriptionRequest(BaseModel):
    url: str

@app.get("/")
async def index(request: Request):
    """Serve the main page."""
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
        print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

# app.py
from flask import Flask, render_template, request, jsonify, make_response
import subprocess
import json
import os
import sys

# Initialize the Flask app
app = Flask(__name__)

# --- Route to serve the main HTML page ---
@app.route('/')
def index():
    """Renders the main user interface page (basic version)."""
    return render_template('index_basic.html')

# --- API Route to handle the transcription process ---
@app.route('/generate-srt', methods=['POST'])
def generate_srt():
    """
    Receives a YouTube URL, spawns a separate process for transcription,
    and returns the SRT file.
    """
    # Try to get JSON data first
    data = request.get_json(silent=True)
    if data and 'url' in data:
        url = data.get('url')
    else:
        # Fallback to form data
        url = request.form.get('url')

    if not url:
        return jsonify({'error': 'URL is required.'}), 400

    try:
        # Spawn a separate Python process for transcription
        # This ensures the model is completely unloaded when the process exits
        result = subprocess.run([
            sys.executable,  # Use the same Python interpreter
            'transcriber.py',  # Run the transcriber script
            url,  # Pass the URL as argument
            '--model-size', 'medium'  # Use medium model size
        ], 
        capture_output=True,  # Capture output
        text=True,  # Return text instead of bytes
        timeout=300  # 5 minute timeout
        )
        
        # Check if the process completed successfully
        if result.returncode != 0:
            # Try to parse error from stderr
            error_msg = result.stderr.strip() if result.stderr else "Transcription failed"
            return jsonify({'error': error_msg}), 500
        
        # Parse the JSON output from the transcription process
        try:
            # Clean the output - remove any leading/trailing whitespace
            stdout_clean = result.stdout.strip()
            
            # Debug: log what we're trying to parse
            print(f"DEBUG: Raw stdout: {repr(stdout_clean)}", file=sys.stderr)
            
            if not stdout_clean:
                return jsonify({'error': 'No output from transcription process'}), 500
            
            output_data = json.loads(stdout_clean)
            
            if not output_data.get('success', False):
                error_msg = output_data.get('error', 'Transcription failed')
                return jsonify({'error': error_msg}), 500
            
            # Get the SRT content
            srt_content = output_data.get('result', '')
            
            if not srt_content:
                return jsonify({'error': 'No transcription content generated'}), 500
            
            # Create a response that the browser will treat as a file download
            response = make_response(srt_content)
            response.headers['Content-Disposition'] = 'attachment; filename=transcription.srt'
            response.mimetype = 'text/plain'
            
            return response
            
        except json.JSONDecodeError as e:
            # Log the problematic output for debugging
            print(f"ERROR: Failed to parse JSON. Raw output: {repr(result.stdout)}", file=sys.stderr)
            print(f"ERROR: stderr output: {repr(result.stderr)}", file=sys.stderr)
            return jsonify({'error': f'Failed to parse transcription output: {e}. Check server logs for details.'}), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Transcription timed out after 5 minutes'}), 500
    except subprocess.CalledProcessError as e:
        return jsonify({'error': f'Transcription process failed: {e}'}), 500
    except Exception as e:
        return jsonify({'error': f'An unexpected error occurred: {e}'}), 500

# --- Main entry point for running the app ---
if __name__ == '__main__':
    # Use port 8080 for broader compatibility
    app.run(host='0.0.0.0', port=8080, debug=True)

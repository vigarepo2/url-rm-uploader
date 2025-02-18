from flask import Flask, request, render_template_string, redirect, url_for, send_from_directory, jsonify, flash
import os
import requests
from werkzeug.utils import secure_filename
from datetime import datetime
import threading

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Configuration
UPLOAD_FOLDER = "temp_downloads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Store download status
downloads_status = {}

def download_file_async(url, filename):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192
        downloaded = 0

        with open(filepath, 'wb') as file:
            for data in response.iter_content(block_size):
                downloaded += len(data)
                file.write(data)
                # Update download progress
                if total_size:
                    progress = int((downloaded / total_size) * 100)
                    downloads_status[filename] = {
                        'status': 'downloading',
                        'progress': progress
                    }

        downloads_status[filename] = {'status': 'completed', 'progress': 100}
    except Exception as e:
        downloads_status[filename] = {'status': 'failed', 'error': str(e)}

# HTML template (all in one file)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>File Download Manager</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .progress {
            height: 20px;
        }
        .download-item {
            margin-bottom: 10px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/">File Download Manager</a>
        </div>
    </nav>

    <div class="container mt-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="row">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5>Download New File</h5>
                    </div>
                    <div class="card-body">
                        <form method="post">
                            <div class="mb-3">
                                <label class="form-label">Download URL</label>
                                <input type="url" class="form-control" name="url" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Custom Filename (optional)</label>
                                <input type="text" class="form-control" name="custom_filename">
                            </div>
                            <button type="submit" class="btn btn-primary">Start Download</button>
                        </form>
                    </div>
                </div>
            </div>

            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5>Active Downloads</h5>
                    </div>
                    <div class="card-body" id="downloads-list">
                        {% for filename, info in downloads.items() %}
                            <div class="download-item">
                                <h6>{{ filename }}</h6>
                                <div class="progress">
                                    <div class="progress-bar" role="progressbar" 
                                         style="width: {{ info.progress }}%"
                                         aria-valuenow="{{ info.progress }}" 
                                         aria-valuemin="0" 
                                         aria-valuemax="100">
                                        {{ info.progress }}%
                                    </div>
                                </div>
                                <small class="text-muted">Status: {{ info.status }}</small>
                                {% if info.status == 'completed' %}
                                    <a href="{{ url_for('download_file', filename=filename) }}" 
                                       class="btn btn-sm btn-success mt-2">
                                        <i class="fas fa-download"></i> Download
                                    </a>
                                {% endif %}
                            </div>
                        {% endfor %}
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script>
        function updateDownloads() {
            $.get('/status', function(data) {
                $('#downloads-list').load(location.href + ' #downloads-list>*');
            });
        }
        setInterval(updateDownloads, 1000);
    </script>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form.get("url")
        custom_filename = request.form.get("custom_filename")
        
        if url:
            try:
                filename = secure_filename(custom_filename if custom_filename 
                    else os.path.basename(url) or f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                
                # Start download in background
                thread = threading.Thread(
                    target=download_file_async,
                    args=(url, filename)
                )
                thread.daemon = True
                thread.start()
                
                downloads_status[filename] = {'status': 'starting', 'progress': 0}
                flash("Download started!", "success")
                
            except Exception as e:
                flash(f"Error: {str(e)}", "error")
                
        return redirect(url_for("index"))
    
    return render_template_string(HTML_TEMPLATE, downloads=downloads_status)

@app.route("/status")
def get_status():
    return jsonify(downloads_status)

@app.route("/download/<filename>")
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

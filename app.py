from flask import Flask, request, render_template_string, redirect, url_for, send_from_directory, jsonify, flash
import os
import requests
from werkzeug.utils import secure_filename
from datetime import datetime
import threading
import urllib.parse
import re

app = Flask(__name__)
app.secret_key = "supersecretkey"

UPLOAD_FOLDER = "temp_downloads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

downloads_status = {}

def get_filename_from_url(url, response):
    # Try to get filename from Content-Disposition header
    if 'Content-Disposition' in response.headers:
        content_disp = response.headers['Content-Disposition']
        matches = re.findall('filename="?([^"]+)"?', content_disp)
        if matches:
            return urllib.parse.unquote(matches[0])

    # Try to get filename from URL path
    path = urllib.parse.unquote(urllib.parse.urlparse(url).path)
    if path and '/' in path:
        return path.split('/')[-1]

    # Try to get filename from URL parameters
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    if 'file' in query:
        return urllib.parse.unquote(query['file'][0])

    return None

def download_file_async(url, filename):
    try:
        response = requests.get(url, stream=True, allow_redirects=True)
        response.raise_for_status()
        
        # Try to get the real filename
        detected_filename = get_filename_from_url(url, response)
        if detected_filename:
            filename = secure_filename(detected_filename)
        
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192
        downloaded = 0

        with open(filepath, 'wb') as file:
            for data in response.iter_content(block_size):
                downloaded += len(data)
                file.write(data)
                if total_size:
                    progress = int((downloaded / total_size) * 100)
                    downloads_status[filename] = {
                        'status': 'downloading',
                        'progress': progress,
                        'size': total_size,
                        'downloaded': downloaded
                    }

        downloads_status[filename] = {
            'status': 'completed',
            'progress': 100,
            'size': total_size,
            'downloaded': total_size
        }
    except Exception as e:
        downloads_status[filename] = {'status': 'failed', 'error': str(e)}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DDL Downloader</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            background-color: #f8f9fa;
        }
        .card {
            box-shadow: 0 0 15px rgba(0,0,0,0.1);
            border: none;
            border-radius: 10px;
        }
        .card-header {
            background-color: #fff;
            border-bottom: 1px solid #eee;
        }
        .progress {
            height: 10px;
            border-radius: 5px;
        }
        .download-item {
            background-color: #fff;
            margin-bottom: 15px;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }
        .navbar {
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .btn-primary {
            background-color: #0d6efd;
            border: none;
        }
        .btn-primary:hover {
            background-color: #0b5ed7;
        }
        .filename {
            word-break: break-all;
            font-weight: 500;
        }
        .size-info {
            font-size: 0.8rem;
            color: #6c757d;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark mb-4">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="fas fa-download me-2"></i>DDL Downloader
            </a>
        </div>
    </nav>

    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="row">
            <div class="col-md-12 mb-4">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0"><i class="fas fa-link me-2"></i>New Download</h5>
                    </div>
                    <div class="card-body">
                        <form method="post" class="row g-3">
                            <div class="col-md-9">
                                <input type="url" class="form-control" name="url" 
                                       placeholder="Enter download URL" required>
                            </div>
                            <div class="col-md-3">
                                <button type="submit" class="btn btn-primary w-100">
                                    <i class="fas fa-download me-2"></i>Start Download
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>

            <div class="col-md-12">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0"><i class="fas fa-tasks me-2"></i>Downloads</h5>
                    </div>
                    <div class="card-body" id="downloads-list">
                        {% for filename, info in downloads.items() %}
                            <div class="download-item">
                                <div class="d-flex justify-content-between align-items-center mb-2">
                                    <h6 class="filename mb-0">{{ filename }}</h6>
                                    {% if info.status == 'completed' %}
                                        <a href="{{ url_for('download_file', filename=filename) }}" 
                                           class="btn btn-sm btn-success">
                                            <i class="fas fa-download me-1"></i>Download
                                        </a>
                                    {% endif %}
                                </div>
                                <div class="progress mb-2">
                                    <div class="progress-bar progress-bar-striped {% if info.status == 'downloading' %}progress-bar-animated{% endif %}"
                                         role="progressbar" 
                                         style="width: {{ info.progress }}%">
                                    </div>
                                </div>
                                <div class="d-flex justify-content-between">
                                    <span class="size-info">
                                        {% if info.size %}
                                            {{ (info.downloaded / 1024 / 1024)|round(2) }} MB / 
                                            {{ (info.size / 1024 / 1024)|round(2) }} MB
                                        {% endif %}
                                    </span>
                                    <span class="badge {% if info.status == 'completed' %}bg-success{% elif info.status == 'failed' %}bg-danger{% else %}bg-primary{% endif %}">
                                        {{ info.status|title }}
                                    </span>
                                </div>
                            </div>
                        {% endfor %}
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
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
        
        if url:
            try:
                # Start with a temporary filename
                temp_filename = f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                thread = threading.Thread(
                    target=download_file_async,
                    args=(url, temp_filename)
                )
                thread.daemon = True
                thread.start()
                
                downloads_status[temp_filename] = {
                    'status': 'starting',
                    'progress': 0,
                    'size': 0,
                    'downloaded': 0
                }
                flash("Download started!", "success")
                
            except Exception as e:
                flash(f"Error: {str(e)}", "danger")
                
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

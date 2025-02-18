from flask import Flask, request, render_template_string, redirect, url_for, send_from_directory, jsonify, flash
import os
import requests
from werkzeug.utils import secure_filename
from datetime import datetime
import threading
import urllib.parse
import re
import hashlib

app = Flask(__name__)
app.secret_key = "supersecretkey"

UPLOAD_FOLDER = "temp_downloads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

downloads_status = {}
file_mappings = {}  # Store custom URL mappings

def get_file_hash(filepath):
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def check_duplicate_file(filepath):
    if not os.path.exists(filepath):
        return False
    new_hash = get_file_hash(filepath)
    for filename in os.listdir(UPLOAD_FOLDER):
        if filename != os.path.basename(filepath):
            existing_file = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.exists(existing_file):
                if get_file_hash(existing_file) == new_hash:
                    return True
    return False

def get_filename_from_url(url, response):
    try:
        # Try Content-Disposition header
        if 'Content-Disposition' in response.headers:
            cd = response.headers['Content-Disposition']
            if 'filename=' in cd:
                filename = re.findall('filename="?([^"]+)"?', cd)[0]
                return urllib.parse.unquote(filename)
        
        # Try URL path
        path = urllib.parse.unquote(urllib.parse.urlparse(url).path)
        if path and '/' in path:
            return path.split('/')[-1]
    except:
        pass
    return None

def download_file_async(url, save_filename, original_filename):
    try:
        response = requests.get(url, stream=True, allow_redirects=True)
        response.raise_for_status()
        
        filepath = os.path.join(UPLOAD_FOLDER, save_filename)
        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192
        downloaded = 0

        with open(filepath, 'wb') as file:
            for data in response.iter_content(block_size):
                downloaded += len(data)
                file.write(data)
                if total_size:
                    progress = int((downloaded / total_size) * 100)
                    downloads_status[save_filename] = {
                        'status': 'downloading',
                        'progress': progress,
                        'size': total_size,
                        'downloaded': downloaded,
                        'original_name': original_filename
                    }

        if check_duplicate_file(filepath):
            os.remove(filepath)
            downloads_status[save_filename] = {
                'status': 'duplicate',
                'error': 'File already exists'
            }
        else:
            downloads_status[save_filename] = {
                'status': 'completed',
                'progress': 100,
                'size': total_size,
                'downloaded': total_size,
                'original_name': original_filename
            }
    except Exception as e:
        downloads_status[save_filename] = {
            'status': 'failed',
            'error': str(e),
            'original_name': original_filename
        }

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FDL Server</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; }
        .navbar { background-color: #1a237e !important; }
        .card {
            border: none;
            border-radius: 10px;
            box-shadow: 0 2px 15px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .progress {
            height: 8px;
            border-radius: 4px;
        }
        .download-item {
            background: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            border: 1px solid #eee;
        }
        .custom-url {
            font-family: monospace;
            background: #f8f9fa;
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 0.9em;
        }
        .btn-rename {
            padding: 2px 8px;
            font-size: 0.8em;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark mb-4">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="fas fa-bolt me-2"></i>FDL Server
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
            <div class="col-12">
                <div class="card">
                    <div class="card-header bg-white">
                        <h5 class="mb-0"><i class="fas fa-download me-2"></i>New Download</h5>
                    </div>
                    <div class="card-body">
                        <form method="post" class="row g-3">
                            <div class="col-md-8">
                                <input type="url" class="form-control" name="url" 
                                       placeholder="Enter download URL" required>
                            </div>
                            <div class="col-md-2">
                                <input type="text" class="form-control" name="custom_url" 
                                       placeholder="Custom URL path">
                            </div>
                            <div class="col-md-2">
                                <button type="submit" class="btn btn-primary w-100">
                                    <i class="fas fa-download me-2"></i>Download
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>

            <div class="col-12">
                <div class="card">
                    <div class="card-header bg-white">
                        <h5 class="mb-0"><i class="fas fa-list me-2"></i>Downloads</h5>
                    </div>
                    <div class="card-body" id="downloads-list">
                        {% for filename, info in downloads.items() %}
                            <div class="download-item">
                                <div class="d-flex justify-content-between align-items-center mb-2">
                                    <h6 class="mb-0">{{ info.get('original_name', filename) }}</h6>
                                    <div>
                                        {% if info.status == 'completed' %}
                                            <button class="btn btn-sm btn-outline-primary btn-rename me-2" 
                                                    onclick="renameFile('{{ filename }}')">
                                                <i class="fas fa-edit"></i>
                                            </button>
                                            <a href="{{ url_for('download_file', filename=filename) }}" 
                                               class="btn btn-sm btn-success">
                                                <i class="fas fa-download me-1"></i>Download
                                            </a>
                                            <button class="btn btn-sm btn-danger ms-2" 
                                                    onclick="deleteFile('{{ filename }}')">
                                                <i class="fas fa-trash"></i>
                                            </button>
                                        {% endif %}
                                    </div>
                                </div>
                                {% if info.status == 'completed' and filename in file_mappings %}
                                    <div class="custom-url mb-2">
                                        {{ request.host_url }}download/{{ file_mappings[filename] }}
                                    </div>
                                {% endif %}
                                <div class="progress mb-2">
                                    <div class="progress-bar {% if info.status == 'downloading' %}progress-bar-striped progress-bar-animated{% endif %}"
                                         role="progressbar" 
                                         style="width: {{ info.progress if info.progress else 0 }}%">
                                    </div>
                                </div>
                                <div class="d-flex justify-content-between align-items-center">
                                    <small class="text-muted">
                                        {% if info.size %}
                                            {{ (info.downloaded / 1024 / 1024)|round(2) }} MB / 
                                            {{ (info.size / 1024 / 1024)|round(2) }} MB
                                        {% endif %}
                                    </small>
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

        function renameFile(filename) {
            const newName = prompt("Enter new filename:");
            if (newName) {
                $.post('/rename/' + filename, {new_name: newName}, function(response) {
                    if (response.status === 'success') {
                        location.reload();
                    } else {
                        alert('Error: ' + response.message);
                    }
                });
            }
        }

        function deleteFile(filename) {
            if (confirm('Are you sure you want to delete this file?')) {
                $.post('/delete/' + filename, function(response) {
                    if (response.status === 'success') {
                        location.reload();
                    }
                });
            }
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
        custom_url = request.form.get("custom_url")
        
        if url:
            try:
                response = requests.head(url, allow_redirects=True)
                original_filename = get_filename_from_url(url, response) or f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                save_filename = secure_filename(original_filename)
                
                if custom_url:
                    file_mappings[save_filename] = custom_url
                
                thread = threading.Thread(
                    target=download_file_async,
                    args=(url, save_filename, original_filename)
                )
                thread.daemon = True
                thread.start()
                
                downloads_status[save_filename] = {
                    'status': 'starting',
                    'progress': 0,
                    'size': 0,
                    'downloaded': 0,
                    'original_name': original_filename
                }
                flash("Download started!", "success")
                
            except Exception as e:
                flash(f"Error: {str(e)}", "danger")
                
        return redirect(url_for("index"))
    
    return render_template_string(HTML_TEMPLATE, downloads=downloads_status, file_mappings=file_mappings)

@app.route("/status")
def get_status():
    return jsonify(downloads_status)

@app.route("/download/<path:filename>")
def download_file(filename):
    # Check if it's a custom URL
    for real_filename, custom_url in file_mappings.items():
        if custom_url == filename:
            return send_from_directory(UPLOAD_FOLDER, real_filename, as_attachment=True)
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

@app.route("/rename/<filename>", methods=["POST"])
def rename_file(filename):
    new_name = request.form.get("new_name")
    if not new_name:
        return jsonify({"status": "error", "message": "No new name provided"})
    
    try:
        old_path = os.path.join(UPLOAD_FOLDER, filename)
        new_path = os.path.join(UPLOAD_FOLDER, secure_filename(new_name))
        os.rename(old_path, new_path)
        
        # Update status and mappings
        if filename in downloads_status:
            downloads_status[secure_filename(new_name)] = downloads_status.pop(filename)
        if filename in file_mappings:
            file_mappings[secure_filename(new_name)] = file_mappings.pop(filename)
            
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/delete/<filename>", methods=["POST"])
def delete_file(filename):
    try:
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            if filename in downloads_status:
                del downloads_status[filename]
            if filename in file_mappings:
                del file_mappings[filename]
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

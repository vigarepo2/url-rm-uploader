from flask import Flask, request, render_template_string, redirect, url_for, send_from_directory, jsonify, flash
import os
import pymongo
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Needed for flash messages

# 🔹 Configuration using Environment Variables
UPLOAD_FOLDER = "uploads"
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "wikram_urls")

# 🔹 Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 🔹 MongoDB Connection (Error Handling)
mongo_enabled = True
try:
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.server_info()  # Test connection
    db = client[DB_NAME]
    files_collection = db["urls"]
except Exception:
    mongo_enabled = False
    db = None
    files_collection = None

# 🔹 Allow all file types
def allowed_file(filename):
    return True  # No restrictions

# 🔹 Home Page (Upload Form)
@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file part", "error")
            return redirect(url_for("upload_file"))
        
        file = request.files["file"]
        custom_name = request.form.get("custom_name")

        if file.filename == "":
            flash("No selected file", "error")
            return redirect(url_for("upload_file"))

        if file:
            filename = secure_filename(custom_name) if custom_name else secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)

            if mongo_enabled:
                file_data = {"filename": filename, "filepath": filepath, "size": os.path.getsize(filepath)}
                files_collection.insert_one(file_data)

            flash("File uploaded successfully!", "success")
            return redirect(url_for("list_tasks"))

    return render_template_string(BASE_HTML, mongo_enabled=mongo_enabled)

# 🔹 Show All Uploaded Files
@app.route("/tasks")
def list_tasks():
    files = []
    if mongo_enabled:
        files = list(files_collection.find({}, {"_id": 0}))

    return render_template_string(TASKS_HTML, files=files, mongo_enabled=mongo_enabled)

# 🔹 Download Files
@app.route("/download/<filename>")
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

# 🔹 Delete Files
@app.route("/delete/<filename>", methods=["POST"])
def delete_file(filename):
    if mongo_enabled:
        file_record = files_collection.find_one({"filename": filename})
        if file_record:
            os.remove(file_record["filepath"])
            files_collection.delete_one({"filename": filename})
            return jsonify({"status": "success", "message": f"{filename} deleted"})
    
    return jsonify({"status": "error", "message": "File not found"})

# 🔹 Run App
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)

# 🔹 HTML Templates Embedded in the Code

BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>File Manager</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            text-align: center;
        }
        nav {
            background-color: #333;
            padding: 10px;
        }
        nav a {
            color: white;
            text-decoration: none;
            margin: 0 15px;
        }
        .warning {
            color: yellow;
            font-weight: bold;
        }
        table {
            width: 80%;
            margin: auto;
            border-collapse: collapse;
        }
        th, td {
            padding: 10px;
            border: 1px solid black;
        }
    </style>
</head>
<body>
    <nav>
        <a href="/">Upload</a>
        <a href="/tasks">Uploaded Files</a>
        {% if not mongo_enabled %}
            <span class="warning">⚠ MongoDB Not Connected</span>
        {% endif %}
    </nav>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            <div>
                {% for category, message in messages %}
                    <p class="{{ category }}">{{ message }}</p>
                {% endfor %}
            </div>
        {% endif %}
    {% endwith %}
    {% block content %}{% endblock %}
</body>
</html>
"""

TASKS_HTML = """
{% extends "base.html" %}
{% block content %}
<h2>Uploaded Files</h2>
<table>
    <tr><th>Filename</th><th>Size (bytes)</th><th>Download</th><th>Delete</th></tr>
    {% for file in files %}
    <tr>
        <td>{{ file.filename }}</td>
        <td>{{ file.size }}</td>
        <td><a href="/download/{{ file.filename }}">Download</a></td>
        <td>
            <form action="/delete/{{ file.filename }}" method="post">
                <button type="submit">Delete</button>
            </form>
        </td>
    </tr>
    {% endfor %}
</table>
{% endblock %}
"""

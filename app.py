from flask import Flask, request, render_template, redirect, url_for, send_from_directory, jsonify, flash
import os
import pymongo
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Needed for flash messages

# Configuration
UPLOAD_FOLDER = "uploads"
MONGO_URI = "mongodb+srv://viga:viga@cluster0.bael7c5.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
DB_NAME = "wikram_urls"

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# MongoDB Connection (Error Handling)
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

# Allow all file types
def allowed_file(filename):
    return True  # No restrictions

# Home Page (Upload Form)
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

    return render_template("upload.html", mongo_enabled=mongo_enabled)

# Show All Uploaded Files
@app.route("/tasks")
def list_tasks():
    files = []
    if mongo_enabled:
        files = list(files_collection.find({}, {"_id": 0}))

    return render_template("tasks.html", files=files, mongo_enabled=mongo_enabled)

# Download Files
@app.route("/download/<filename>")
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

# Delete Files
@app.route("/delete/<filename>", methods=["POST"])
def delete_file(filename):
    if mongo_enabled:
        file_record = files_collection.find_one({"filename": filename})
        if file_record:
            os.remove(file_record["filepath"])
            files_collection.delete_one({"filename": filename})
            return jsonify({"status": "success", "message": f"{filename} deleted"})
    
    return jsonify({"status": "error", "message": "File not found"})

# Run App
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)

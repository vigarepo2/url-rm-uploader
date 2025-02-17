# Use Python 3.9
FROM python:3.9

# Set the working directory
WORKDIR /app

# Copy project files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose Flask Port
EXPOSE 5000

# Set default environment variables
ENV MONGO_URI=mongodb+srv://viga:viga@cluster0.bael7c5.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0
ENV DB_NAME=wikram_urls

# Run the Flask app
CMD ["python", "app.py"]

FROM python:3.9

WORKDIR /app

# Install requirements
RUN pip install flask requests werkzeug

# Copy application
COPY app.py .

# Create temp downloads directory
RUN mkdir -p temp_downloads

EXPOSE 5000

CMD ["python3", "app.py"]

FROM python:3.9
WORKDIR /app
COPY . .
RUN pip install flask pymongo werkzeug
CMD ["python", "app.py"]

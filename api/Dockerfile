FROM python:3.12-slim
RUN useradd -r -u 10001 sift && mkdir /app /data && chown sift /data
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py schema.sql ./
USER sift
CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8000","--no-server-header"]

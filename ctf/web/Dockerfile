FROM python:3.12-slim
RUN useradd -m ctf
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
USER ctf
CMD ["python", "app.py"]

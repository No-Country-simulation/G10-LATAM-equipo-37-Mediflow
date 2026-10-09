FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY ui /app/ui
EXPOSE 8501
CMD ["streamlit", "run", "ui/app.py", "--server.port", "8501", "--server.address", "0.0.0.0", "--server.headless", "true"]

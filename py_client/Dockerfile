FROM python:3.9-slim

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

EXPOSE 8080

# Command to run the FastAPI application using Uvicorn
# Ensure main_ui.py is at the root of what's copied to /app
CMD ["uvicorn", "main_ui:app", "--host", "0.0.0.0", "--port", "8080"]

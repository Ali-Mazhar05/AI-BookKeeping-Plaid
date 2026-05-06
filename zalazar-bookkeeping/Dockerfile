FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set environment variables
ENV PYTHONPATH=src
ENV PORT=7860

# Expose the port Hugging Face expects
EXPOSE 7860

# Run the application
CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "7860"]

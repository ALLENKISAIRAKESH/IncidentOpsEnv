FROM python:3.10-slim

# Set up a non-root user to run the app, required by Hugging Face Spaces
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

# Copy dependencies first for caching
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy the rest of the application
COPY --chown=user:user . .

# Hugging Face Spaces routing defaults to port 7860
EXPOSE 7860
ENV GRADIO_SERVER_NAME="0.0.0.0"

ENV ENABLE_WEB_INTERFACE=true
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]

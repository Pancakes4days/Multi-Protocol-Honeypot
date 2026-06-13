FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Create logs directory
RUN mkdir -p /logs

# Copy honeypot script
COPY minecraft_honeypot.py /app/

# Make script executable
RUN chmod +x /app/minecraft_honeypot.py

# Expose Minecraft port
EXPOSE 25565

# Run the honeypot
CMD ["python3", "/app/minecraft_honeypot.py"]

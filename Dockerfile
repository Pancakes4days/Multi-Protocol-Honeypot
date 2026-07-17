FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Create an unprivileged user to run the honeypot, plus the logs directory
# it needs write access to. The service never runs as root.
RUN useradd --system --no-create-home --shell /usr/sbin/nologin honeypot \
    && mkdir -p /logs \
    && chown honeypot:honeypot /logs

# Copy honeypot script
COPY minecraft_honeypot.py /app/

# Expose Minecraft port
EXPOSE 25565

# Drop privileges
USER honeypot

# Run the honeypot (unbuffered so logs stream promptly)
CMD ["python3", "-u", "/app/minecraft_honeypot.py"]

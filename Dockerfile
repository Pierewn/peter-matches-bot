FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Matches bot code
COPY matches_bot.py .
COPY digit_analyzer.py .
COPY digit_patterns.py .
COPY digit_confidence.py .
COPY strategies/ strategies/
COPY execution/ execution/

# Run Matches bot
CMD ["python", "matches_bot.py"]

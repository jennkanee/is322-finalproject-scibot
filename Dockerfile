# Use an official Python base image
FROM python:3.11

# Set environment variables to ensure Python outputs all logs
ENV PYTHONUNBUFFERED=1

# Set the working directory in the Docker container
WORKDIR /app

# Copy application requirements file into the image
COPY requirements.txt /app/

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code into the image
COPY . /app

# Command to run the bot when the container starts
CMD ["python", "-u", "bot.py"]

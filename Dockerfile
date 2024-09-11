# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY src/ .

# Install any needed packages specified in requirements.txt
RUN apt-get update && apt-get install -y ffmpeg
RUN pip install --no-cache-dir -r requirements.txt

# Run api.py when the container launches
CMD ["fastapi", "dev", "api.py"]

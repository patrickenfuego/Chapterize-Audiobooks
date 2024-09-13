# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Copy the requirements file into the container
COPY requirements.txt ./

# Install the dependencies specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Define the entrypoint
ENTRYPOINT ["python", "chapterize_ab.py"]

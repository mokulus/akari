
# Use the official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.10-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Copy local code to the container image.
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

# Install production dependencies.
RUN apt-get update
RUN apt-get install -y binutils build-essential
RUN python3 -m pip install -r requirements.txt

# Run the web service on container startup. Here we use the gunicorn
# webserver, with one worker process and 8 threads.
# For environments with multiple CPU cores, increase the number of workers
# to be equal to the cores available.
# Timeout is set to 0 to disable the timeouts of the workers to allow Cloud Run to handle instance scaling.
WORKDIR $APP_HOME/src
CMD exec python3 -m gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
# CMD exec python3 -m gunicorn --bind :$PORT --timeout 0 main:app
# CMD exec python3 akari.py
# CMD flask --app akari/main run

# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 8501 available to the world outside this container
EXPOSE 8501

# Define environment variable (Streamlit needs this)
ENV STREAMLIT_SERVER_PORT=8501

# Run calories_counter.py when the container launches
CMD ["streamlit", "run", "calories_counter.py", "--server.address=0.0.0.0", "--server.port=8501"]
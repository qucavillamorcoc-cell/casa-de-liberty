# use a slim Python base image
FROM python:3.11-slim

# install system packages that your app needs
RUN apt-get update && \
    apt-get install -y default-mysql-client libpq5 && \
    rm -rf /var/lib/apt/lists/*

# set working directory and copy project files
WORKDIR /app
COPY . .

# install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# collect static files if you use them
# RUN python manage.py collectstatic --noinput

# default command (Railway will set PORT env)
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:$PORT"]
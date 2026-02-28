# use a slim Python base image matching Django 6 requirements
FROM python:3.12-slim

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

# default command (Railway sets PORT). Use shell form so ${PORT} expands.
CMD ["sh", "-c", "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120"]

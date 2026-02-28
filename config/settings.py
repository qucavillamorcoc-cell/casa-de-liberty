from pathlib import Path
import os
import sys
import socket
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-)k69t8s!a*l=w7rnl0*gc@ddrn!glfa9iafrs%gbf!!3nux^=p')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True') == 'True'

# Detect local Django dev server (`python manage.py runserver`) so we don't
# force HTTPS on a server that only speaks HTTP.
IS_RUNSERVER = any(arg.startswith('runserver') for arg in sys.argv)
IS_LOCAL_HTTPS_DEV = os.getenv('LOCAL_HTTPS_DEV', '0') == '1'
SERVE_MEDIA_IN_DEV = DEBUG or IS_RUNSERVER or IS_LOCAL_HTTPS_DEV

def _detect_local_ipv4():
    """Best-effort local LAN IPv4 detection for local-device testing."""
    candidates = []
    try:
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.connect(("8.8.8.8", 80))
        candidates.append(udp.getsockname()[0])
        udp.close()
    except OSError:
        pass

    try:
        _, _, host_ips = socket.gethostbyname_ex(socket.gethostname())
        candidates.extend(host_ips)
    except OSError:
        pass

    for ip in candidates:
        if ip and not ip.startswith("127."):
            return ip
    return None


ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]

# Local development override: allow LAN access from phone/tablet when using runserver.
if IS_RUNSERVER or IS_LOCAL_HTTPS_DEV:
    for host in ('localhost', '127.0.0.1', '0.0.0.0', '[::1]', '*'):
        if host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(host)

LOCAL_LAN_IP = _detect_local_ipv4()
if LOCAL_LAN_IP and LOCAL_LAN_IP not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(LOCAL_LAN_IP)

# Railway-provided public domain support
RAILWAY_PUBLIC_DOMAIN = os.getenv('RAILWAY_PUBLIC_DOMAIN', '').strip()
if RAILWAY_PUBLIC_DOMAIN:
    if RAILWAY_PUBLIC_DOMAIN not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(RAILWAY_PUBLIC_DOMAIN)
    # Allow all Railway generated subdomains unless explicitly restricted
    if '.up.railway.app' not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append('.up.railway.app')

# CSRF Configuration for development - allow requests from local network
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://localhost:8001',
    'http://127.0.0.1:8001',
    'https://localhost:8000',
    'https://127.0.0.1:8000',
    'https://localhost:8443',
    'https://127.0.0.1:8443',
    'http://10.0.0.34:8000',  # Your phone's IP
    'http://*.bbrouter:8000',  # Local network
]

if LOCAL_LAN_IP:
    for scheme in ('http', 'https'):
        for port in ('8000', '8001', '8443'):
            origin = f'{scheme}://{LOCAL_LAN_IP}:{port}'
            if origin not in CSRF_TRUSTED_ORIGINS:
                CSRF_TRUSTED_ORIGINS.append(origin)

if RAILWAY_PUBLIC_DOMAIN:
    railway_origin = f'https://{RAILWAY_PUBLIC_DOMAIN}'
    if railway_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(railway_origin)

# Alternative: More permissive for local development (NOT for production!)
# CSRF_TRUSTED_ORIGINS = ['http://*:8000', 'http://*:*']

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # WhiteNoise for static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
DB_ENGINE = os.getenv('DB_ENGINE', 'sqlite3').lower()

if DATABASE_URL:
    parsed = urlparse(DATABASE_URL)
    scheme = (parsed.scheme or '').lower()

    if scheme in ('postgres', 'postgresql', 'postgresql_psycopg2'):
        default_db = {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': unquote((parsed.path or '/').lstrip('/')),
            'USER': unquote(parsed.username or ''),
            'PASSWORD': unquote(parsed.password or ''),
            'HOST': parsed.hostname or 'localhost',
            'PORT': str(parsed.port or 5432),
            'CONN_MAX_AGE': int(os.getenv('DB_CONN_MAX_AGE', '600')),
            'OPTIONS': {
                'sslmode': os.getenv('DB_SSLMODE', 'require'),
            },
        }
        DATABASES = {'default': default_db}
    elif scheme in ('mysql', 'mysql2'):
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.mysql',
                'NAME': unquote((parsed.path or '/').lstrip('/')),
                'USER': unquote(parsed.username or ''),
                'PASSWORD': unquote(parsed.password or ''),
                'HOST': parsed.hostname or 'localhost',
                'PORT': str(parsed.port or 3306),
            }
        }
    elif scheme in ('sqlite', 'sqlite3'):
        db_name = unquote((parsed.path or '/db.sqlite3').lstrip('/'))
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / db_name,
            }
        }
    else:
        # Fallback if DATABASE_URL has an unsupported scheme.
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }
elif DB_ENGINE == 'postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'casadeliberty'),
            'USER': os.getenv('DB_USER', 'postgres'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
            'CONN_MAX_AGE': 600,
        }
    }
elif DB_ENGINE == 'mysql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.getenv('DB_NAME', 'casadeliberty'),
            'USER': os.getenv('DB_USER', 'root'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '3306'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'  # Production static files
STATICFILES_DIRS = [BASE_DIR / 'static']  # Development static files
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'  # Production optimization

# Media files (User uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', 'your-email@gmail.com')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'your-email@gmail.com')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@casadeliberty.com')

# Security Settings (Production)
if not DEBUG:
    SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'True') == 'True'
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'True') == 'True'
    CSRF_COOKIE_SECURE = os.getenv('CSRF_COOKIE_SECURE', 'True') == 'True'
    SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv('SECURE_HSTS_INCLUDE_SUBDOMAINS', 'True') == 'True'
    SECURE_HSTS_PRELOAD = os.getenv('SECURE_HSTS_PRELOAD', 'True') == 'True'

    # Local dev override: avoid redirecting http://127.0.0.1:8000 to HTTPS,
    # and allow cookies over HTTP when using the dev server.
    if IS_RUNSERVER:
        SECURE_SSL_REDIRECT = False
        SESSION_COOKIE_SECURE = False
        CSRF_COOKIE_SECURE = False
        SECURE_HSTS_SECONDS = 0
        SECURE_HSTS_INCLUDE_SUBDOMAINS = False
        SECURE_HSTS_PRELOAD = False

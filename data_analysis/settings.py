"""
Django settings for data_analysis project (dev).
"""

from pathlib import Path

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent.parent  # <repo_root> (folder with manage.py)

# --- Core ---
SECRET_KEY = 'django-insecure-=t)#kjnu4y#m&2maha+uv*o!ahd1o%f6b%3^+-(6wq(oo=*i28'
DEBUG = True
ALLOWED_HOSTS: list[str] = []

# --- Apps ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'analysis',
]

# --- Middleware ---
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# --- URLs / WSGI ---
ROOT_URLCONF = 'data_analysis.urls'
WSGI_APPLICATION = 'data_analysis.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Look in BOTH locations:
        #  - <BASE_DIR>\templates  (same folder as manage.py)
        #  - <BASE_DIR>\..\templates (one level up)
        'DIRS': [
            (BASE_DIR / 'templates'),
            (BASE_DIR.parent / 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.static',
            ],
        },
    },
]

# --- Database ---
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# --- Auth validators ---
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- I18N / TZ ---
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Johannesburg'   # local time
USE_I18N = True
USE_TZ = True


# --- Static files ---
STATIC_URL = "static/"

# dev assets live here:  <…\data_analysis_project\data_analysis\static>
STATICFILES_DIRS = [BASE_DIR / "static"]

# optional (only used by collectstatic)
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

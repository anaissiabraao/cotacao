# Configuração do Gunicorn para Render
import multiprocessing
import os

# Configurações de Workers
workers = int(os.getenv('WEB_CONCURRENCY', multiprocessing.cpu_count() * 2 + 1))
threads = int(os.getenv('PYTHON_MAX_THREADS', 4))
worker_class = 'gthread'
worker_connections = 1000

# Timeouts
timeout = 120
keepalive = 5

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Performance
max_requests = 1000
max_requests_jitter = 50
graceful_timeout = 120

# Buffer
forwarded_allow_ips = '*'
proxy_allow_ips = '*'
secure_scheme_headers = {
    'X-FORWARDED-PROTOCOL': 'ssl',
    'X-FORWARDED-PROTO': 'https',
    'X-FORWARDED-SSL': 'on'
}

# Configurações do processo
preload_app = True
reload = False
daemon = False

# Cache
sendfile = True

# Bind
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"

# Logs
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"' 
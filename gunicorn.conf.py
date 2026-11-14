# Gunicorn Production Config — IN NET CREATIONS · MDDS
# Usage: gunicorn -c gunicorn.conf.py server:app

import multiprocessing, os

# Server socket
bind    = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
backlog = 2048

# Workers: 2-4 per CPU core
workers     = int(os.environ.get("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"
threads     = 4          # threads per worker (handles concurrent requests)
timeout     = 120        # seconds before killing a stalled worker
keepalive   = 5          # keep idle connections alive (seconds)
max_requests       = 1000   # restart worker after 1000 requests (memory leak guard)
max_requests_jitter = 100   # randomise restart to avoid thundering herd

# Logging
accesslog = "-"   # stdout
errorlog  = "-"   # stdout
loglevel  = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sµs'

# Security
limit_request_line   = 4096
limit_request_fields = 100
limit_request_field_size = 8190


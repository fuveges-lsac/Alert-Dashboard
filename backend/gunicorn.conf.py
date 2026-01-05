import multiprocessing
import os

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = os.getenv("LOG_LEVEL", "info")
proc_name = "alert-intelligence"
daemon = False
pidfile = "logs/gunicorn.pid"

def on_starting(server):
    print(f"🚀 Starting Alert Intelligence with {workers} workers")

"""
Gunicorn configuration file for production deployment
"""
import multiprocessing
import os

# Server Socket
bind = "0.0.0.0:8090"
backlog = 2048

# Worker Processes
workers = int(os.environ.get('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = os.environ.get('GUNICORN_WORKER_CLASS', 'gevent')
worker_connections = int(os.environ.get('GUNICORN_WORKER_CONNECTIONS', 1000))
threads = int(os.environ.get('GUNICORN_THREADS', 2))
max_requests = int(os.environ.get('GUNICORN_MAX_REQUESTS', 1000))
max_requests_jitter = int(os.environ.get('GUNICORN_MAX_REQUESTS_JITTER', 50))
timeout = int(os.environ.get('GUNICORN_TIMEOUT', 300))
graceful_timeout = int(os.environ.get('GUNICORN_GRACEFUL_TIMEOUT', 30))
keepalive = int(os.environ.get('GUNICORN_KEEPALIVE', 5))

# Restart workers after this many seconds
max_worker_age = 3600

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Server Mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Logging
errorlog = '-'
loglevel = os.environ.get('LOG_LEVEL', 'info')
accesslog = '-'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process Naming
proc_name = 'fda-rag-backend'

# Server Hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("Starting FDA RAG Backend Server")
    server.log.info(f"Workers: {workers}")
    server.log.info(f"Worker Class: {worker_class}")
    server.log.info(f"Worker Connections: {worker_connections}")
    server.log.info(f"Threads per Worker: {threads}")

def when_ready(server):
    """Called just after the server is started."""
    server.log.info("FDA RAG Backend Server is ready. Listening at: %s", server.address)

def worker_int(worker):
    """Called when a worker receives the INT or QUIT signal."""
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    server.log.info("Pre-fork worker")

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def pre_exec(server):
    """Called just before a new master process is forked."""
    server.log.info("Forked child, re-executing.")

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("Reloading workers")

def worker_abort(worker):
    """Called when a worker process times out."""
    worker.log.info("Worker timeout, aborting")

def on_exit(server):
    """Called just before exiting."""
    server.log.info("Shutting down FDA RAG Backend Server")

# Environment-specific configuration
def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    worker.log.info("Worker initialized (pid: %s)", worker.pid)
    
    # Import here to ensure it's done after fork
    from database.database import engine
    
    # Dispose of any existing connections from parent process
    engine.dispose()
    
    # Configure SQLAlchemy pool for this worker
    engine.pool._recycle = 3600  # Recycle connections after 1 hour
    engine.pool._timeout = 30    # Connection timeout
    engine.pool._size = 5        # Pool size per worker
    engine.pool._max_overflow = 10  # Max overflow connections
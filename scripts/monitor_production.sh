#!/bin/bash

# Production Monitoring Script for FDA RAG Pipeline
# This script monitors the health and performance of production services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
LOG_DIR="/var/log/fda-rag"
ALERT_EMAIL="${ALERT_EMAIL:-}"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_DIR/monitor.log"
}

# Function to send alerts (if email configured)
send_alert() {
    local subject="$1"
    local message="$2"
    
    if [ -n "$ALERT_EMAIL" ]; then
        echo "$message" | mail -s "[FDA RAG Alert] $subject" "$ALERT_EMAIL"
    fi
}

# Check if services are running
check_services() {
    log "Checking service status..."
    
    local services=("fda-mysql" "fda-backend" "fda-frontend" "fda-nginx" "fda-redis")
    local failed_services=()
    
    for service in "${services[@]}"; do
        if docker ps --filter "name=$service" --filter "status=running" | grep -q "$service"; then
            echo -e "${GREEN}✓${NC} $service is running"
        else
            echo -e "${RED}✗${NC} $service is not running"
            failed_services+=("$service")
        fi
    done
    
    if [ ${#failed_services[@]} -gt 0 ]; then
        send_alert "Services Down" "The following services are not running: ${failed_services[*]}"
        return 1
    fi
    
    return 0
}

# Check service health
check_health() {
    log "Checking service health..."
    
    # Check backend API
    if curl -sf http://localhost:8090/health > /dev/null; then
        echo -e "${GREEN}✓${NC} Backend API is healthy"
    else
        echo -e "${RED}✗${NC} Backend API health check failed"
        send_alert "Backend Unhealthy" "Backend API health check failed"
    fi
    
    # Check frontend
    if curl -sf http://localhost:3001 > /dev/null; then
        echo -e "${GREEN}✓${NC} Frontend is responding"
    else
        echo -e "${RED}✗${NC} Frontend not responding"
        send_alert "Frontend Unhealthy" "Frontend not responding"
    fi
    
    # Check MySQL
    if docker exec fda-mysql mysqladmin ping -h localhost > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} MySQL is healthy"
    else
        echo -e "${RED}✗${NC} MySQL health check failed"
        send_alert "MySQL Unhealthy" "MySQL health check failed"
    fi
}

# Check resource usage
check_resources() {
    log "Checking resource usage..."
    
    echo -e "\n${YELLOW}Container Resource Usage:${NC}"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" \
        fda-mysql fda-backend fda-frontend fda-nginx fda-redis 2>/dev/null || true
    
    # Check disk usage
    echo -e "\n${YELLOW}Disk Usage:${NC}"
    df -h | grep -E "/$|/var/lib/docker" || true
    
    # Check specific volume sizes
    echo -e "\n${YELLOW}Docker Volume Sizes:${NC}"
    for volume in mysql-data chromadb-data downloads-data uploads-data; do
        size=$(docker run --rm -v ${COMPOSE_FILE%.*}_${volume}:/data alpine du -sh /data 2>/dev/null | cut -f1 || echo "N/A")
        echo "$volume: $size"
    done
}

# Check database connections
check_db_connections() {
    log "Checking database connections..."
    
    local connections=$(docker exec fda-mysql mysql -u root -p${MYSQL_ROOT_PASSWORD} -e "SHOW STATUS LIKE 'Threads_connected';" -s -N 2>/dev/null | awk '{print $2}' || echo "0")
    local max_connections=$(docker exec fda-mysql mysql -u root -p${MYSQL_ROOT_PASSWORD} -e "SHOW VARIABLES LIKE 'max_connections';" -s -N 2>/dev/null | awk '{print $2}' || echo "0")
    
    echo -e "${YELLOW}Database Connections:${NC} $connections / $max_connections"
    
    if [ "$connections" -gt $((max_connections * 80 / 100)) ]; then
        echo -e "${RED}Warning:${NC} Database connection pool is over 80% utilized"
        send_alert "High DB Connections" "Database connections: $connections / $max_connections (>80%)"
    fi
}

# Check error logs
check_error_logs() {
    log "Checking error logs..."
    
    echo -e "\n${YELLOW}Recent Errors (last 10 minutes):${NC}"
    
    # Backend errors
    local backend_errors=$(docker logs fda-backend --since 10m 2>&1 | grep -iE "error|exception|critical" | wc -l)
    echo "Backend errors: $backend_errors"
    
    # MySQL errors
    local mysql_errors=$(docker logs fda-mysql --since 10m 2>&1 | grep -iE "error|exception" | grep -v "Found existing" | wc -l)
    echo "MySQL errors: $mysql_errors"
    
    # Nginx errors
    local nginx_errors=$(docker logs fda-nginx --since 10m 2>&1 | grep -iE "error|emerg|alert|crit" | wc -l)
    echo "Nginx errors: $nginx_errors"
    
    if [ $((backend_errors + mysql_errors + nginx_errors)) -gt 10 ]; then
        send_alert "High Error Rate" "High error rate detected in logs"
    fi
}

# Performance metrics
check_performance() {
    log "Checking performance metrics..."
    
    # API response time check
    echo -e "\n${YELLOW}API Response Time:${NC}"
    response_time=$(curl -o /dev/null -s -w '%{time_total}' http://localhost:8090/health || echo "N/A")
    echo "Health endpoint: ${response_time}s"
    
    # Check slow queries (if MySQL slow log is enabled)
    if docker exec fda-mysql test -f /var/log/mysql/slow.log 2>/dev/null; then
        slow_queries=$(docker exec fda-mysql wc -l < /var/log/mysql/slow.log 2>/dev/null || echo "0")
        echo -e "${YELLOW}Slow queries (total):${NC} $slow_queries"
    fi
}

# Main monitoring function
monitor() {
    echo -e "${GREEN}=== FDA RAG Production Monitor ===${NC}"
    echo "Timestamp: $(date)"
    echo "Environment: Production"
    echo ""
    
    check_services || true
    echo ""
    check_health || true
    echo ""
    check_resources || true
    echo ""
    check_db_connections || true
    echo ""
    check_error_logs || true
    echo ""
    check_performance || true
    
    echo -e "\n${GREEN}=== Monitor Complete ===${NC}"
}

# Run monitoring based on command
case "${1:-}" in
    "once")
        monitor
        ;;
    "continuous")
        log "Starting continuous monitoring (every 5 minutes)"
        while true; do
            monitor
            echo -e "\n${YELLOW}Sleeping for 5 minutes...${NC}\n"
            sleep 300
        done
        ;;
    "alert-test")
        send_alert "Test Alert" "This is a test alert from FDA RAG monitoring"
        echo "Test alert sent"
        ;;
    *)
        echo "Usage: $0 {once|continuous|alert-test}"
        echo "  once       - Run monitoring once"
        echo "  continuous - Run monitoring every 5 minutes"
        echo "  alert-test - Send a test alert"
        exit 1
        ;;
esac
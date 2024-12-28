"""
WebSocket Health Monitor - Background task for maintaining WebSocket connection health
"""

import asyncio
import logging
from datetime import datetime
from api.services.websocket_manager import get_connection_manager

logger = logging.getLogger(__name__)


class WebSocketHealthMonitor:
    """
    Monitors WebSocket connection health and performs periodic cleanup.
    """
    
    def __init__(self, check_interval: int = 30):
        """
        Initialize the health monitor.
        
        Args:
            check_interval: Seconds between health checks (default: 30)
        """
        self.check_interval = check_interval
        self.connection_manager = get_connection_manager()
        self.is_running = False
        self._task = None
        
    async def start(self):
        """Start the health monitoring task."""
        if self.is_running:
            logger.warning("WebSocket health monitor is already running")
            return
            
        self.is_running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"WebSocket health monitor started (interval: {self.check_interval}s)")
        
    async def stop(self):
        """Stop the health monitoring task."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("WebSocket health monitor stopped")
        
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self.is_running:
            try:
                await asyncio.sleep(self.check_interval)
                
                # Perform health check
                health_stats = await self.connection_manager.health_check()
                
                # Log health status
                logger.debug(
                    f"WebSocket health check: "
                    f"total={health_stats['total_connections']}, "
                    f"healthy={health_stats['healthy_connections']}, "
                    f"unhealthy={health_stats['unhealthy_connections']}, "
                    f"channels={health_stats['active_channels']}"
                )
                
                # Clean up stale connections
                cleaned = await self.connection_manager.cleanup_stale_connections()
                if cleaned > 0:
                    logger.info(f"Cleaned up {cleaned} stale WebSocket connections")
                
                # Alert if too many unhealthy connections
                if health_stats['unhealthy_connections'] > 10:
                    logger.warning(
                        f"High number of unhealthy WebSocket connections: "
                        f"{health_stats['unhealthy_connections']}"
                    )
                    
            except Exception as e:
                logger.error(f"Error in WebSocket health monitor: {str(e)}")
                # Continue monitoring even if there's an error
                
    async def force_cleanup(self) -> int:
        """
        Force an immediate cleanup of stale connections.
        
        Returns:
            Number of connections cleaned up
        """
        logger.info("Forcing WebSocket connection cleanup")
        return await self.connection_manager.cleanup_stale_connections()


# Global health monitor instance
_health_monitor = None


def get_health_monitor() -> WebSocketHealthMonitor:
    """Get the global WebSocket health monitor instance."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = WebSocketHealthMonitor()
    return _health_monitor


async def start_websocket_health_monitoring():
    """Start the WebSocket health monitoring background task."""
    monitor = get_health_monitor()
    await monitor.start()


async def stop_websocket_health_monitoring():
    """Stop the WebSocket health monitoring background task."""
    monitor = get_health_monitor()
    await monitor.stop()
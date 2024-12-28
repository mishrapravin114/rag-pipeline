"""
WebSocket Connection Manager - Handles WebSocket connections for real-time updates
"""

import asyncio
import json
import logging
from typing import Dict, List, Set, Optional, Any
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from enum import Enum

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """WebSocket message types"""
    PROGRESS = "progress"
    STATUS = "status"
    ERROR = "error"
    COMPLETE = "complete"
    PING = "ping"
    PONG = "pong"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates.
    Supports channel-based subscriptions and broadcasting.
    """
    
    def __init__(self):
        """Initialize the connection manager."""
        # Channel-based connections: {channel_id: [websocket1, websocket2, ...]}
        self._connections: Dict[str, List[WebSocket]] = {}
        # Connection metadata: {websocket_id: {channel, user_id, connected_at, ...}}
        self._connection_metadata: Dict[int, Dict[str, Any]] = {}
        # Active channels
        self._active_channels: Set[str] = set()
        # Connection health tracking
        self._connection_health: Dict[int, Dict[str, Any]] = {}
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        
    async def connect(
        self,
        websocket: WebSocket,
        channel_id: str,
        user_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Accept and register a WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            channel_id: Channel to subscribe to (e.g., "job_123", "collection_456")
            user_id: Optional user ID for authentication
            metadata: Optional additional metadata
            
        Returns:
            True if connection was successful
        """
        try:
            await websocket.accept()
            
            async with self._lock:
                # Add to channel
                if channel_id not in self._connections:
                    self._connections[channel_id] = []
                    self._active_channels.add(channel_id)
                
                self._connections[channel_id].append(websocket)
                
                # Store metadata
                ws_id = id(websocket)
                self._connection_metadata[ws_id] = {
                    "channel": channel_id,
                    "user_id": user_id,
                    "connected_at": datetime.utcnow().isoformat(),
                    "metadata": metadata or {},
                    "message_count": 0
                }
                
                # Initialize health tracking
                self._connection_health[ws_id] = {
                    "last_ping": datetime.utcnow(),
                    "last_pong": datetime.utcnow(),
                    "failed_pings": 0,
                    "is_alive": True
                }
            
            # Send connection confirmation
            await self._send_to_websocket(websocket, {
                "type": MessageType.CONNECTED.value,
                "channel": channel_id,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            logger.info(f"WebSocket connected: channel={channel_id}, user={user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect WebSocket: {str(e)}")
            return False
    
    async def disconnect(self, websocket: WebSocket) -> None:
        """
        Remove a WebSocket connection and clean up.
        
        Args:
            websocket: The WebSocket connection to remove
        """
        ws_id = id(websocket)
        
        async with self._lock:
            # Get metadata before removal
            metadata = self._connection_metadata.get(ws_id, {})
            channel_id = metadata.get("channel")
            
            if channel_id and channel_id in self._connections:
                # Remove from channel
                self._connections[channel_id] = [
                    ws for ws in self._connections[channel_id] 
                    if id(ws) != ws_id
                ]
                
                # Clean up empty channels
                if not self._connections[channel_id]:
                    del self._connections[channel_id]
                    self._active_channels.discard(channel_id)
            
            # Clean up metadata
            self._connection_metadata.pop(ws_id, None)
            self._connection_health.pop(ws_id, None)
        
        logger.info(f"WebSocket disconnected: channel={channel_id}")
    
    async def broadcast_to_channel(
        self,
        channel_id: str,
        message: Dict[str, Any],
        exclude_websocket: Optional[WebSocket] = None
    ) -> int:
        """
        Broadcast a message to all connections in a channel.
        
        Args:
            channel_id: Channel to broadcast to
            message: Message to send
            exclude_websocket: Optional WebSocket to exclude from broadcast
            
        Returns:
            Number of successful sends
        """
        if channel_id not in self._connections:
            return 0
        
        # Get current connections snapshot
        connections = self._connections[channel_id].copy()
        
        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.utcnow().isoformat()
        
        successful_sends = 0
        failed_connections = []
        
        for websocket in connections:
            if exclude_websocket and websocket == exclude_websocket:
                continue
            
            try:
                await self._send_to_websocket(websocket, message)
                successful_sends += 1
            except Exception as e:
                logger.error(f"Failed to send to WebSocket: {str(e)}")
                failed_connections.append(websocket)
        
        # Clean up failed connections
        for ws in failed_connections:
            await self.disconnect(ws)
        
        return successful_sends
    
    async def send_to_websocket(
        self,
        websocket: WebSocket,
        message: Dict[str, Any]
    ) -> bool:
        """
        Send a message to a specific WebSocket connection.
        
        Args:
            websocket: Target WebSocket
            message: Message to send
            
        Returns:
            True if successful
        """
        try:
            await self._send_to_websocket(websocket, message)
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {str(e)}")
            await self.disconnect(websocket)
            return False
    
    async def _send_to_websocket(
        self,
        websocket: WebSocket,
        message: Dict[str, Any]
    ) -> None:
        """Internal method to send message and update metadata."""
        await websocket.send_json(message)
        
        # Update message count
        ws_id = id(websocket)
        if ws_id in self._connection_metadata:
            self._connection_metadata[ws_id]["message_count"] += 1
    
    async def handle_client_message(
        self,
        websocket: WebSocket,
        message: str
    ) -> None:
        """
        Handle incoming messages from client.
        
        Args:
            websocket: Source WebSocket
            message: Received message
        """
        try:
            data = json.loads(message) if isinstance(message, str) else message
            message_type = data.get("type")
            
            if message_type == MessageType.PING.value:
                # Respond to ping
                await self.send_to_websocket(websocket, {
                    "type": MessageType.PONG.value,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                # Update health tracking
                ws_id = id(websocket)
                if ws_id in self._connection_health:
                    self._connection_health[ws_id]["last_pong"] = datetime.utcnow()
                    self._connection_health[ws_id]["failed_pings"] = 0
            
            elif message_type == "subscribe":
                # Handle channel subscription changes
                new_channel = data.get("channel")
                if new_channel:
                    await self._change_channel(websocket, new_channel)
            
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {message}")
        except Exception as e:
            logger.error(f"Error handling client message: {str(e)}")
    
    async def _change_channel(
        self,
        websocket: WebSocket,
        new_channel: str
    ) -> None:
        """Change the channel subscription for a WebSocket."""
        ws_id = id(websocket)
        
        async with self._lock:
            if ws_id in self._connection_metadata:
                old_channel = self._connection_metadata[ws_id]["channel"]
                
                # Remove from old channel
                if old_channel in self._connections:
                    self._connections[old_channel] = [
                        ws for ws in self._connections[old_channel]
                        if id(ws) != ws_id
                    ]
                
                # Add to new channel
                if new_channel not in self._connections:
                    self._connections[new_channel] = []
                self._connections[new_channel].append(websocket)
                
                # Update metadata
                self._connection_metadata[ws_id]["channel"] = new_channel
    
    async def send_progress_update(
        self,
        job_id: str,
        progress_data: Dict[str, Any]
    ) -> int:
        """
        Send progress update for a specific job.
        
        Args:
            job_id: Job ID (used as channel)
            progress_data: Progress information
            
        Returns:
            Number of clients notified
        """
        message = {
            "type": MessageType.PROGRESS.value,
            "jobId": job_id,
            "data": progress_data
        }
        
        return await self.broadcast_to_channel(job_id, message)
    
    async def send_error(
        self,
        channel_id: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Send error message to a channel.
        
        Args:
            channel_id: Target channel
            error_message: Error message
            error_details: Optional additional error details
            
        Returns:
            Number of clients notified
        """
        message = {
            "type": MessageType.ERROR.value,
            "error": error_message,
            "details": error_details or {}
        }
        
        return await self.broadcast_to_channel(channel_id, message)
    
    async def send_completion(
        self,
        job_id: str,
        completion_data: Dict[str, Any]
    ) -> int:
        """
        Send completion notification for a job.
        
        Args:
            job_id: Job ID (used as channel)
            completion_data: Completion information
            
        Returns:
            Number of clients notified
        """
        message = {
            "type": MessageType.COMPLETE.value,
            "jobId": job_id,
            "data": completion_data
        }
        
        return await self.broadcast_to_channel(job_id, message)
    
    def get_channel_connections(self, channel_id: str) -> int:
        """Get number of active connections for a channel."""
        return len(self._connections.get(channel_id, []))
    
    def get_active_channels(self) -> List[str]:
        """Get list of active channels."""
        return list(self._active_channels)
    
    def get_connection_info(self, websocket: WebSocket) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific connection."""
        ws_id = id(websocket)
        return self._connection_metadata.get(ws_id)
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all connections.
        
        Returns:
            Health status report
        """
        total_connections = sum(len(conns) for conns in self._connections.values())
        healthy_connections = 0
        unhealthy_connections = 0
        
        # Check each connection
        for channel_id, connections in self._connections.items():
            for ws in connections:
                ws_id = id(ws)
                if ws_id in self._connection_health:
                    if self._connection_health[ws_id]["is_alive"]:
                        healthy_connections += 1
                    else:
                        unhealthy_connections += 1
        
        return {
            "total_connections": total_connections,
            "healthy_connections": healthy_connections,
            "unhealthy_connections": unhealthy_connections,
            "active_channels": len(self._active_channels),
            "channels": list(self._active_channels)
        }
    
    async def cleanup_stale_connections(self) -> int:
        """
        Clean up stale connections based on health checks.
        
        Returns:
            Number of connections cleaned up
        """
        stale_connections = []
        
        for channel_id, connections in self._connections.items():
            for ws in connections:
                ws_id = id(ws)
                if ws_id in self._connection_health:
                    health = self._connection_health[ws_id]
                    # Consider connection stale if no pong for 60 seconds
                    if (datetime.utcnow() - health["last_pong"]).total_seconds() > 60:
                        stale_connections.append(ws)
        
        # Disconnect stale connections
        for ws in stale_connections:
            await self.disconnect(ws)
        
        return len(stale_connections)


# Global connection manager instance
connection_manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance."""
    return connection_manager
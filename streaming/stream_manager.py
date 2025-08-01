# streaming/stream_manager.py - Generic streaming infrastructure with asset-specific processing
import logging
import threading
from typing import Optional, Callable, Dict, Any
from .subscription_manager import SubscriptionManager

logger = logging.getLogger(__name__)

class StreamManager:
    """Generic streaming manager that can work with any streaming client"""
    
    def __init__(self):
        self.streamer = None
        self.socketio = None
        self.is_streaming = False
        self.subscription_manager = SubscriptionManager()
        self.message_handler: Optional[Callable] = None
        self.stream_thread: Optional[threading.Thread] = None
        
    def set_dependencies(self, streamer, socketio):
        """Inject streaming dependencies"""
        self.streamer = streamer
        self.socketio = socketio
    
    def set_message_handler(self, handler: Callable[[Dict[str, Any]], None]):
        """Set the message handler for incoming stream data"""
        self.message_handler = handler
    
    def start_streaming(self) -> bool:
        """Start the streaming connection"""
        if not self.streamer:
            logger.error("No streamer configured")
            return False
            
        if self.is_streaming:
            logger.info("Streaming already active")
            return True
            
        try:
            # Start the actual streamer with our message processor
            if hasattr(self.streamer, 'start'):
                self.streamer.start(self._process_raw_message)
                logger.info("Streamer started with message handler")
            else:
                logger.warning("Streamer does not have start() method")
                
            self.is_streaming = True
            logger.info("Starting stream manager")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start streaming: {e}")
            self.is_streaming = False
            return False
    
    def stop_streaming(self):
        """Stop the streaming connection"""
        if not self.is_streaming:
            return
            
        try:
            # Stop the actual streamer
            if hasattr(self.streamer, 'stop'):
                self.streamer.stop()
                logger.info("Streamer stopped")
                
            self.is_streaming = False
            if self.stream_thread and self.stream_thread.is_alive():
                self.stream_thread.join(timeout=5)
            logger.info("Stopped stream manager")
            
        except Exception as e:
            logger.error(f"Error stopping streaming: {e}")
    
    def add_subscription(self, symbol: str, callback: Optional[Callable] = None) -> bool:
        """Add a symbol subscription"""
        return self.subscription_manager.add_subscription(symbol, callback)
    
    def remove_subscription(self, symbol: str) -> bool:
        """Remove a symbol subscription"""
        return self.subscription_manager.remove_subscription(symbol)
    
    def get_subscriptions(self):
        """Get all current subscriptions"""
        return self.subscription_manager.get_subscriptions()
    
    def clear_subscriptions(self):
        """Clear all subscriptions"""
        self.subscription_manager.clear_subscriptions()
    
    def process_message(self, message: Dict[str, Any]):
        """Process incoming stream message"""
        if self.message_handler:
            try:
                self.message_handler(message)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
        else:
            logger.warning("No message handler configured")
    
    def is_active(self) -> bool:
        """Check if streaming is active"""
        return self.is_streaming
    
    def _process_raw_message(self, raw_message: str):
        """Process raw message from streamer and convert to dict"""
        try:
            import json
            if isinstance(raw_message, str):
                message_data = json.loads(raw_message)
            else:
                message_data = raw_message
                
            # Pass to message handler
            if self.message_handler:
                self.message_handler(message_data)
            else:
                logger.warning("No message handler configured for raw message")
                
        except Exception as e:
            logger.error(f"Error processing raw message: {e}")
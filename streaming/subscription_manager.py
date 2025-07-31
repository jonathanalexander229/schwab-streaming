# streaming/subscription_manager.py - Handle symbol subscriptions
import logging
from typing import Set, Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)

class SubscriptionManager:
    """Generic subscription manager for any type of streaming data"""
    
    def __init__(self):
        self.subscribed_symbols: Set[str] = set()
        self.subscription_callbacks: Dict[str, Callable] = {}
    
    def add_subscription(self, symbol: str, callback: Optional[Callable] = None) -> bool:
        """Add a symbol to subscriptions"""
        try:
            if symbol in self.subscribed_symbols:
                logger.info(f"Symbol {symbol} already subscribed")
                return True
                
            self.subscribed_symbols.add(symbol)
            if callback:
                self.subscription_callbacks[symbol] = callback
                
            logger.info(f"Added subscription for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add subscription for {symbol}: {e}")
            return False
    
    def remove_subscription(self, symbol: str) -> bool:
        """Remove a symbol from subscriptions"""
        try:
            if symbol not in self.subscribed_symbols:
                logger.info(f"Symbol {symbol} not subscribed")
                return True
                
            self.subscribed_symbols.discard(symbol)
            self.subscription_callbacks.pop(symbol, None)
            
            logger.info(f"Removed subscription for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove subscription for {symbol}: {e}")
            return False
    
    def get_subscriptions(self) -> Set[str]:
        """Get all current subscriptions"""
        return self.subscribed_symbols.copy()
    
    def clear_subscriptions(self):
        """Clear all subscriptions"""
        self.subscribed_symbols.clear()
        self.subscription_callbacks.clear()
        logger.info("Cleared all subscriptions")
    
    def is_subscribed(self, symbol: str) -> bool:
        """Check if symbol is subscribed"""
        return symbol in self.subscribed_symbols
    
    def get_callback(self, symbol: str) -> Optional[Callable]:
        """Get callback for a specific symbol"""
        return self.subscription_callbacks.get(symbol)
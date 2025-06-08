# core/feature_manager.py - Centralized feature initialization
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class FeatureManager:
    """Manages feature initialization and configuration"""
    
    def __init__(self, data_dir: str, socketio):
        self.data_dir = data_dir
        self.socketio = socketio
        self.features: Dict[str, Any] = {}
        self.is_mock_mode = False
        
    def initialize_market_data(self, schwab_client, schwab_streamer, is_mock_mode: bool = False):
        """Initialize market data feature"""
        try:
            from market_data import get_market_data_manager
            
            self.is_mock_mode = is_mock_mode
            manager = get_market_data_manager(self.data_dir)
            manager.set_dependencies(schwab_client, schwab_streamer, self.socketio, is_mock_mode)
            
            self.features['market_data'] = manager
            logger.info(f"Market data feature initialized (mock_mode: {is_mock_mode})")
            return manager
            
        except Exception as e:
            logger.error(f"Failed to initialize market data: {e}")
            return None
    
    def get_feature(self, feature_name: str):
        """Get an initialized feature"""
        return self.features.get(feature_name)
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a feature is enabled"""
        return feature_name in self.features
    
    def get_mock_mode(self) -> bool:
        """Get current mock mode status"""
        return self.is_mock_mode
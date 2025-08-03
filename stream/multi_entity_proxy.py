"""
Multi-Entity Proxy Framework
"""
import asyncio
import logging
import multiprocessing
from typing import List, Optional, Dict, Any
from pathlib import Path

from stream.proxy_server import ProxyServer
from debug import get_debug_manager


class MultiEntityProxy:
    """
    Multi-entity proxy framework that maintains the same execution path
    as a single entity but supports multiple concurrent accounts.
    """
    
    def __init__(self, entities_config: List[Dict[str, Any]], debug_enabled: bool = False):
        """
        Initialize multi-entity proxy.
        
        Args:
            entities_config: List of entity configurations
            debug_enabled: Whether debugging is enabled
        """
        self.entities_config = entities_config
        self.debug_enabled = debug_enabled
        self.debug_manager = get_debug_manager(debug_enabled)
        self.entities = {}  # entity_id -> ProxyServer instance
        self.entity_queues = {}  # entity_id -> multiprocessing.Queue
        self.logger = logging.getLogger('multi_entity_proxy')
        
        # Initialize entities
        self._initialize_entities()
    
    def _initialize_entities(self):
        """Initialize all proxy entities based on configuration."""
        for config in self.entities_config:
            entity_id = config.get('id', f"entity_{len(self.entities)}")
            host = config.get('host', '127.0.0.1')
            port = config.get('port', 3120 + len(self.entities))
            intercept_domains = config.get('intercept_domains', ['*.google.com'])
            upstream_proxy = config.get('upstream_proxy', None)
            
            # Create queue for this entity
            queue = multiprocessing.Queue() if config.get('use_queue', False) else None
            
            # Create proxy server instance
            proxy_server = ProxyServer(
                host=host,
                port=port,
                intercept_domains=intercept_domains,
                upstream_proxy=upstream_proxy,
                queue=queue
            )
            
            # Store entity
            self.entities[entity_id] = proxy_server
            if queue:
                self.entity_queues[entity_id] = queue
                
            self.logger.info(f"Initialized entity {entity_id} on {host}:{port}")
    
    async def start_entity(self, entity_id: str):
        """
        Start a specific entity.
        
        Args:
            entity_id: ID of the entity to start
        """
        if entity_id not in self.entities:
            raise ValueError(f"Entity {entity_id} not found")
            
        proxy_server = self.entities[entity_id]
        
        # Capture debug data
        if self.debug_enabled:
            debug_data = {
                "action": "start_entity",
                "host": proxy_server.host,
                "port": proxy_server.port,
                "intercept_domains": proxy_server.intercept_domains,
                "upstream_proxy": proxy_server.upstream_proxy
            }
            self.debug_manager.capture_data("entity_startup", entity_id, debug_data)
        
        try:
            self.logger.info(f"Starting entity {entity_id} on {proxy_server.host}:{proxy_server.port}")
            await proxy_server.start()
        except Exception as e:
            self.logger.error(f"Error starting entity {entity_id}: {e}")
            if self.debug_enabled:
                error_data = {
                    "action": "start_entity_error",
                    "error": str(e)
                }
                self.debug_manager.capture_data("entity_startup", entity_id, error_data)
            raise
    
    async def start_all_entities(self):
        """Start all entities concurrently."""
        tasks = []
        for entity_id in self.entities:
            task = asyncio.create_task(self.start_entity(entity_id))
            tasks.append(task)
            
        # Capture debug data
        if self.debug_enabled:
            debug_data = {
                "action": "start_all_entities",
                "entity_count": len(self.entities),
                "entity_ids": list(self.entities.keys())
            }
            self.debug_manager.capture_data("pipeline_startup", "multi_entity", debug_data)
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            self.logger.error(f"Error starting entities: {e}")
            if self.debug_enabled:
                error_data = {
                    "action": "start_all_entities_error",
                    "error": str(e)
                }
                self.debug_manager.capture_data("pipeline_startup", "multi_entity", error_data)
            raise
    
    def get_entity_queue(self, entity_id: str) -> Optional[multiprocessing.Queue]:
        """
        Get the queue for a specific entity.
        
        Args:
            entity_id: ID of the entity
            
        Returns:
            Queue for the entity or None if not configured
        """
        return self.entity_queues.get(entity_id)
    
    def get_entity_info(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific entity.
        
        Args:
            entity_id: ID of the entity
            
        Returns:
            Dictionary with entity information or None if not found
        """
        if entity_id not in self.entities:
            return None
            
        proxy_server = self.entities[entity_id]
        return {
            "id": entity_id,
            "host": proxy_server.host,
            "port": proxy_server.port,
            "intercept_domains": proxy_server.intercept_domains,
            "upstream_proxy": proxy_server.upstream_proxy,
            "has_queue": entity_id in self.entity_queues
        }
    
    def get_all_entities_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all entities.
        
        Returns:
            Dictionary mapping entity IDs to their information
        """
        return {entity_id: self.get_entity_info(entity_id) for entity_id in self.entities}


# Example usage function
async def main():
    """Example usage of the multi-entity proxy framework."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Example configuration for multiple entities
    entities_config = [
        {
            "id": "account_1",
            "host": "127.0.0.1",
            "port": 3120,
            "intercept_domains": ["*.google.com"],
            "upstream_proxy": None,
            "use_queue": True
        },
        {
            "id": "account_2",
            "host": "127.0.0.1",
            "port": 3121,
            "intercept_domains": ["*.google.com"],
            "upstream_proxy": None,
            "use_queue": True
        }
    ]
    
    # Create and start multi-entity proxy
    multi_proxy = MultiEntityProxy(entities_config, debug_enabled=True)
    
    try:
        await multi_proxy.start_all_entities()
    except KeyboardInterrupt:
        logging.info("Shutting down multi-entity proxy")
    except Exception as e:
        logging.error(f"Error in multi-entity proxy: {e}")


if __name__ == '__main__':
    asyncio.run(main())

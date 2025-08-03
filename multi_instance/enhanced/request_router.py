"""
Request Router for the Enhanced Multi-Instance System.

This module is responsible for distributing incoming requests to appropriate
browser instances based on various routing strategies.
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, List, Optional, Any, Tuple

from fastapi import Request, HTTPException

from .models import (
    RoutingStrategy,
    RequestContext,
    InstanceStatus
)


class RequestRouter:
    """
    Distributes incoming requests to appropriate browser instances.
    
    Responsibilities:
    - Select an appropriate instance for each incoming request
    - Implement various routing strategies (round-robin, least-loaded, etc.)
    - Handle request retries and failover
    - Track request status and metrics
    - Queue requests when all instances are busy
    """
    
    def __init__(self, instance_manager, logger: Optional[logging.Logger] = None):
        """
        Initialize the request router.
        
        Args:
            instance_manager: Instance manager to use for routing
            logger: Logger instance
        """
        self.instance_manager = instance_manager
        self.logger = logger or logging.getLogger(__name__)
        
        # Routing configuration
        self.routing_strategy = RoutingStrategy.PRIMARY_FIRST
        self.enable_failover = True
        self.request_timeout = 300.0  # 5 minutes
        
        # Request tracking
        self.active_requests: Dict[str, RequestContext] = {}
        self.request_history: List[RequestContext] = []
        self.max_history_size = 1000
        
        # Round-robin counter
        self.round_robin_counter = 0
        
        # Request queue
        self.request_queue = asyncio.Queue()
        self.queue_processing_task = None
        
        # Statistics
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'routing_errors': 0,
            'average_response_time': 0.0,
            'queue_length_max': 0
        }
    
    async def route_request(self, request, http_request: Request) -> Tuple[str, Any]:
        """
        Route a request to an appropriate instance.
        
        Args:
            request: The request to route
            http_request: The HTTP request
            
        Returns:
            Tuple[str, Any]: Request ID and response
        """
        request_id = str(uuid.uuid4())
        client_ip = http_request.client.host if http_request.client else "unknown"
        user_agent = http_request.headers.get("user-agent", "unknown")
        
        # Create request context
        context = RequestContext(
            request_id=request_id,
            instance_id=None,
            model_id=getattr(request, 'model', None),
            started_at=time.time(),
            client_ip=client_ip,
            user_agent=user_agent,
            original_request=request,
            http_request=http_request
        )
        
        self.active_requests[request_id] = context
        self.stats['total_requests'] += 1
        
        self.logger.info(f"[{request_id}] Received request, model: {getattr(request, 'model', 'unknown')}")
        
        try:
            # Select instance
            instance_id = await self._select_instance(context)
            if not instance_id:
                # If no instance is available, queue the request
                if await self._queue_request(context):
                    raise HTTPException(
                        status_code=202,
                        detail=f"[{request_id}] Request queued. Try again later."
                    )
                else:
                    raise HTTPException(
                        status_code=503,
                        detail=f"[{request_id}] Service unavailable. Try again later.",
                        headers={"Retry-After": "30"}
                    )
            
            context.instance_id = instance_id
            self.logger.info(f"[{request_id}] Routing to instance: {instance_id}")
            
            # Process request on selected instance
            response = await self._process_request_on_instance(context)
            
            # Record success
            self._record_success(context)
            
            return request_id, response
            
        except HTTPException:
            self._record_failure(context)
            raise
        except Exception as e:
            self.logger.error(f"[{request_id}] Error processing request: {e}")
            self._record_failure(context)
            raise HTTPException(
                status_code=500,
                detail=f"[{request_id}] Internal server error"
            )
        finally:
            # Clean up request context
            if request_id in self.active_requests:
                del self.active_requests[request_id]
            
            # Add to history (limit size)
            self.request_history.append(context)
            if len(self.request_history) > self.max_history_size:
                self.request_history = self.request_history[-self.max_history_size:]
    
    async def _select_instance(self, context: RequestContext) -> Optional[str]:
        """
        Select an appropriate instance for the request.
        
        Args:
            context: Request context
            
        Returns:
            Optional[str]: Selected instance ID or None if no instance is available
        """
        available_instances = await self.instance_manager.get_available_instances()
        
        if not available_instances:
            self.logger.warning(f"[{context.request_id}] No available instances")
            return None
        
        # Select based on strategy
        if self.routing_strategy == RoutingStrategy.PRIMARY_FIRST:
            return self._select_primary_first(available_instances)
        elif self.routing_strategy == RoutingStrategy.LEAST_LOADED:
            return await self._select_least_loaded(available_instances)
        elif self.routing_strategy == RoutingStrategy.ROUND_ROBIN:
            return self._select_round_robin(available_instances)
        elif self.routing_strategy == RoutingStrategy.RANDOM:
            return self._select_random(available_instances)
        else:
            return available_instances[0]
    
    def _select_primary_first(self, available_instances: List[str]) -> str:
        """
        Select instance using primary-first strategy.
        
        Args:
            available_instances: List of available instance IDs
            
        Returns:
            str: Selected instance ID
        """
        # Look for instance_1 prefixed instances
        primary_instances = [inst for inst in available_instances if inst.startswith('instance_1')]
        
        if primary_instances:
            return primary_instances[0]
        
        # If no primary instance, use the first available
        return available_instances[0]
    
    async def _select_least_loaded(self, available_instances: List[str]) -> str:
        """
        Select instance with the least load.
        
        Args:
            available_instances: List of available instance IDs
            
        Returns:
            str: Selected instance ID
        """
        best_instance = available_instances[0]
        best_load = float('inf')
        
        for instance_id in available_instances:
            instance = await self.instance_manager.get_instance(instance_id)
            if instance:
                runtime = self.instance_manager.runtime_states.get(instance_id)
                if runtime:
                    load = runtime.active_requests / instance.max_concurrent_requests
                    if load < best_load:
                        best_load = load
                        best_instance = instance_id
        
        return best_instance
    
    def _select_round_robin(self, available_instances: List[str]) -> str:
        """
        Select instance using round-robin strategy.
        
        Args:
            available_instances: List of available instance IDs
            
        Returns:
            str: Selected instance ID
        """
        instance = available_instances[self.round_robin_counter % len(available_instances)]
        self.round_robin_counter += 1
        return instance
    
    def _select_random(self, available_instances: List[str]) -> str:
        """
        Select instance randomly.
        
        Args:
            available_instances: List of available instance IDs
            
        Returns:
            str: Selected instance ID
        """
        import random
        return random.choice(available_instances)
    
    async def _queue_request(self, context: RequestContext) -> bool:
        """
        Queue a request for later processing.
        
        Args:
            context: Request context
            
        Returns:
            bool: True if queued successfully
        """
        try:
            # Check if queue processing is running
            if self.queue_processing_task is None or self.queue_processing_task.done():
                self.queue_processing_task = asyncio.create_task(self._process_queue())
            
            # Add to queue
            await self.request_queue.put(context)
            
            # Update stats
            queue_size = self.request_queue.qsize()
            if queue_size > self.stats['queue_length_max']:
                self.stats['queue_length_max'] = queue_size
            
            self.logger.info(f"[{context.request_id}] Request queued, position: {queue_size}")
            return True
            
        except Exception as e:
            self.logger.error(f"[{context.request_id}] Failed to queue request: {e}")
            return False
    
    async def _process_queue(self):
        """Process queued requests."""
        while not self.request_queue.empty():
            try:
                # Get next request
                context = await self.request_queue.get()
                
                # Check if request is still valid
                elapsed = time.time() - context.started_at
                if elapsed > self.request_timeout:
                    self.logger.warning(f"[{context.request_id}] Queued request timed out")
                    self.request_queue.task_done()
                    continue
                
                # Try to find an available instance
                instance_id = await self._select_instance(context)
                if not instance_id:
                    # No instance available, put back in queue
                    await self.request_queue.put(context)
                    await asyncio.sleep(1)
                    continue
                
                # Process request
                context.instance_id = instance_id
                try:
                    await self._process_request_on_instance(context)
                    self._record_success(context)
                except Exception as e:
                    self.logger.error(f"[{context.request_id}] Failed to process queued request: {e}")
                    self._record_failure(context)
                
                self.request_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Error in queue processing: {e}")
                await asyncio.sleep(1)
    
    async def _process_request_on_instance(self, context: RequestContext) -> Any:
        """
        Process a request on the selected instance.
        
        Args:
            context: Request context
            
        Returns:
            Any: Response from the instance
        """
        instance_id = context.instance_id
        
        # TODO: Implement actual request processing
        # This is a placeholder for the actual implementation
        
        self.logger.info(f"[{context.request_id}] Processing request on instance {instance_id}")
        
        # Simulate processing
        await asyncio.sleep(0.1)
        
        return {"status": "success", "message": "Request processed"}
    
    async def set_routing_strategy(self, strategy: RoutingStrategy) -> None:
        """
        Set the routing strategy to use.
        
        Args:
            strategy: Routing strategy to use
        """
        self.routing_strategy = strategy
        self.logger.info(f"Routing strategy set to: {strategy.value}")
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """
        Get the status of the request queue.
        
        Returns:
            Dict[str, Any]: Queue status information
        """
        return {
            "queue_length": self.request_queue.qsize(),
            "max_queue_length": self.stats['queue_length_max']
        }
    
    async def cancel_request(self, request_id: str) -> bool:
        """
        Cancel a queued or in-progress request.
        
        Args:
            request_id: ID of the request to cancel
            
        Returns:
            bool: True if cancelled successfully
        """
        # Check if request is active
        if request_id in self.active_requests:
            # TODO: Implement cancellation logic
            del self.active_requests[request_id]
            self.logger.info(f"[{request_id}] Request cancelled")
            return True
        
        # Request not found
        return False
    
    def _record_success(self, context: RequestContext):
        """
        Record a successful request.
        
        Args:
            context: Request context
        """
        response_time = time.time() - context.started_at
        
        self.stats['successful_requests'] += 1
        
        # Update average response time
        total_requests = self.stats['successful_requests'] + self.stats['failed_requests']
        if total_requests > 0:
            current_avg = self.stats['average_response_time']
            self.stats['average_response_time'] = (
                current_avg * (total_requests - 1) + response_time
            ) / total_requests
        
        self.logger.info(f"[{context.request_id}] Request successful, response time: {response_time:.2f}s")
    
    def _record_failure(self, context: RequestContext):
        """
        Record a failed request.
        
        Args:
            context: Request context
        """
        self.stats['failed_requests'] += 1
        self.logger.warning(f"[{context.request_id}] Request failed")
    
    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get routing metrics and statistics.
        
        Returns:
            Dict[str, Any]: Metrics and statistics
        """
        # Calculate success rate
        total_requests = self.stats['successful_requests'] + self.stats['failed_requests']
        success_rate = (self.stats['successful_requests'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "total_requests": self.stats['total_requests'],
            "successful_requests": self.stats['successful_requests'],
            "failed_requests": self.stats['failed_requests'],
            "success_rate": success_rate,
            "average_response_time": self.stats['average_response_time'],
            "active_requests": len(self.active_requests),
            "queue_length": self.request_queue.qsize(),
            "max_queue_length": self.stats['queue_length_max'],
            "routing_strategy": self.routing_strategy.value,
            "enable_failover": self.enable_failover
        }
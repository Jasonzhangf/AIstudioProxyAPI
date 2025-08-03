"""
Monitoring System for the Enhanced Multi-Instance System.

This module collects metrics and provides insights into the performance and health
of the multi-instance system.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Any


class MonitoringSystem:
    """
    Collects metrics and provides insights into system performance and health.
    
    Responsibilities:
    - Collect metrics from all system components
    - Track instance health and performance
    - Monitor request throughput and latency
    - Detect and report errors
    - Provide a dashboard for system status
    """
    
    def __init__(self, 
                 metrics_dir: str = "logs/metrics",
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the monitoring system.
        
        Args:
            metrics_dir: Directory for metrics storage
            logger: Logger instance
        """
        self.metrics_dir = Path(metrics_dir)
        self.logger = logger or logging.getLogger(__name__)
        
        # Metrics storage
        self.metrics: Dict[str, Any] = {}
        self.counters: Dict[str, int] = {}
        self.gauges: Dict[str, float] = {}
        self.timers: Dict[str, List[float]] = {}
        
        # Request tracking
        self.request_metrics: Dict[str, Dict[str, Any]] = {}
        
        # Error tracking
        self.error_metrics: Dict[str, Dict[str, Any]] = {}
        
        # Instance metrics
        self.instance_metrics: Dict[str, Dict[str, Any]] = {}
        
        # Monitoring task
        self.monitoring_task = None
        self.monitoring_interval = 60  # seconds
        self.is_running = False
        
        # Ensure metrics directory exists
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
    
    async def start(self, interval: int = 60):
        """
        Start the monitoring system.
        
        Args:
            interval: Monitoring interval in seconds
        """
        if self.is_running:
            return
        
        self.monitoring_interval = interval
        self.is_running = True
        
        # Start monitoring task
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        self.logger.info(f"Monitoring system started with interval {interval}s")
    
    async def stop(self):
        """Stop the monitoring system."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Cancel monitoring task
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
            
        self.logger.info("Monitoring system stopped")
    
    async def _monitoring_loop(self):
        """Monitoring loop that periodically collects and saves metrics."""
        try:
            while self.is_running:
                # Collect metrics
                self._collect_system_metrics()
                
                # Save metrics
                self._save_metrics()
                
                # Wait for next interval
                await asyncio.sleep(self.monitoring_interval)
                
        except asyncio.CancelledError:
            self.logger.info("Monitoring loop cancelled")
        except Exception as e:
            self.logger.error(f"Error in monitoring loop: {e}")
            self.is_running = False
    
    def _collect_system_metrics(self):
        """Collect system metrics."""
        try:
            # System metrics
            import psutil
            
            # CPU usage
            self.gauges["system.cpu.percent"] = psutil.cpu_percent()
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.gauges["system.memory.total"] = memory.total
            self.gauges["system.memory.available"] = memory.available
            self.gauges["system.memory.percent"] = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            self.gauges["system.disk.total"] = disk.total
            self.gauges["system.disk.free"] = disk.free
            self.gauges["system.disk.percent"] = disk.percent
            
        except ImportError:
            self.logger.warning("psutil not available, system metrics collection disabled")
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
    
    def _save_metrics(self):
        """Save metrics to file."""
        try:
            # Create metrics data
            metrics_data = {
                "timestamp": time.time(),
                "counters": self.counters,
                "gauges": self.gauges,
                "timers": {k: self._summarize_timer(v) for k, v in self.timers.items()},
                "requests": self.request_metrics,
                "errors": self.error_metrics,
                "instances": self.instance_metrics
            }
            
            # Save to file
            metrics_file = self.metrics_dir / f"metrics_{int(time.time())}.json"
            with open(metrics_file, 'w', encoding='utf-8') as f:
                json.dump(metrics_data, f, indent=2)
            
            # Clean up old metrics files
            self._cleanup_old_metrics()
            
        except Exception as e:
            self.logger.error(f"Error saving metrics: {e}")
    
    def _summarize_timer(self, values: List[float]) -> Dict[str, float]:
        """
        Summarize timer values.
        
        Args:
            values: List of timer values
            
        Returns:
            Dict[str, float]: Summary statistics
        """
        if not values:
            return {"count": 0, "min": 0, "max": 0, "avg": 0, "p95": 0}
        
        # Sort values for percentile calculation
        sorted_values = sorted(values)
        
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "p95": sorted_values[int(len(sorted_values) * 0.95)]
        }
    
    def _cleanup_old_metrics(self):
        """Clean up old metrics files."""
        try:
            # Keep only the last 100 metrics files
            metrics_files = sorted(self.metrics_dir.glob("metrics_*.json"))
            if len(metrics_files) > 100:
                for file in metrics_files[:-100]:
                    file.unlink()
                
        except Exception as e:
            self.logger.error(f"Error cleaning up old metrics: {e}")
    
    def record_metric(self, metric_name: str, value: Any, tags: Optional[Dict[str, str]] = None) -> None:
        """
        Record a metric value.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            tags: Optional tags for the metric
        """
        # Store in metrics dictionary
        if tags:
            metric_key = f"{metric_name}:{','.join(f'{k}={v}' for k, v in tags.items())}"
        else:
            metric_key = metric_name
        
        self.metrics[metric_key] = value
    
    def increment_counter(self, counter_name: str, increment: int = 1, tags: Optional[Dict[str, str]] = None) -> None:
        """
        Increment a counter metric.
        
        Args:
            counter_name: Name of the counter
            increment: Amount to increment by
            tags: Optional tags for the counter
        """
        # Create counter key
        if tags:
            counter_key = f"{counter_name}:{','.join(f'{k}={v}' for k, v in tags.items())}"
        else:
            counter_key = counter_name
        
        # Increment counter
        if counter_key not in self.counters:
            self.counters[counter_key] = 0
        
        self.counters[counter_key] += increment
    
    def record_request(self, request_id: str, instance_id: str, duration_ms: int, success: bool) -> None:
        """
        Record information about a processed request.
        
        Args:
            request_id: Request ID
            instance_id: Instance ID that processed the request
            duration_ms: Request duration in milliseconds
            success: Whether the request was successful
        """
        # Store request metrics
        self.request_metrics[request_id] = {
            "instance_id": instance_id,
            "duration_ms": duration_ms,
            "success": success,
            "timestamp": time.time()
        }
        
        # Update instance metrics
        if instance_id not in self.instance_metrics:
            self.instance_metrics[instance_id] = {
                "requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "total_duration_ms": 0,
                "average_duration_ms": 0
            }
        
        instance_metrics = self.instance_metrics[instance_id]
        instance_metrics["requests"] += 1
        if success:
            instance_metrics["successful_requests"] += 1
        else:
            instance_metrics["failed_requests"] += 1
        
        instance_metrics["total_duration_ms"] += duration_ms
        instance_metrics["average_duration_ms"] = (
            instance_metrics["total_duration_ms"] / instance_metrics["requests"]
        )
        
        # Record timer
        timer_key = f"request.duration:{instance_id}"
        if timer_key not in self.timers:
            self.timers[timer_key] = []
        
        self.timers[timer_key].append(duration_ms)
        
        # Limit timer values
        if len(self.timers[timer_key]) > 1000:
            self.timers[timer_key] = self.timers[timer_key][-1000:]
    
    def record_error(self, instance_id: str, error_type: str, error_message: str) -> None:
        """
        Record an error that occurred.
        
        Args:
            instance_id: Instance ID where the error occurred
            error_type: Type of error
            error_message: Error message
        """
        error_id = f"error_{int(time.time())}_{len(self.error_metrics)}"
        
        # Store error metrics
        self.error_metrics[error_id] = {
            "instance_id": instance_id,
            "error_type": error_type,
            "error_message": error_message,
            "timestamp": time.time()
        }
        
        # Increment error counter
        self.increment_counter("errors", 1, {"instance_id": instance_id, "type": error_type})
    
    def get_metrics(self, metric_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get current metrics.
        
        Args:
            metric_names: Optional list of metric names to get
            
        Returns:
            Dict[str, Any]: Current metrics
        """
        if metric_names:
            return {k: v for k, v in self.metrics.items() if k in metric_names}
        else:
            return {
                "counters": self.counters,
                "gauges": self.gauges,
                "timers": {k: self._summarize_timer(v) for k, v in self.timers.items()},
                "requests": {
                    "total": sum(1 for m in self.request_metrics.values()),
                    "successful": sum(1 for m in self.request_metrics.values() if m["success"]),
                    "failed": sum(1 for m in self.request_metrics.values() if not m["success"])
                },
                "errors": {
                    "total": len(self.error_metrics),
                    "by_type": self._count_errors_by_type()
                },
                "instances": self.instance_metrics
            }
    
    def _count_errors_by_type(self) -> Dict[str, int]:
        """
        Count errors by type.
        
        Returns:
            Dict[str, int]: Error counts by type
        """
        counts = {}
        for error in self.error_metrics.values():
            error_type = error["error_type"]
            counts[error_type] = counts.get(error_type, 0) + 1
        return counts
    
    def get_instance_metrics(self, instance_id: str) -> Dict[str, Any]:
        """
        Get metrics for a specific instance.
        
        Args:
            instance_id: Instance ID
            
        Returns:
            Dict[str, Any]: Instance metrics
        """
        # Get instance metrics
        instance_metrics = self.instance_metrics.get(instance_id, {})
        
        # Get instance requests
        instance_requests = {
            k: v for k, v in self.request_metrics.items()
            if v["instance_id"] == instance_id
        }
        
        # Get instance errors
        instance_errors = {
            k: v for k, v in self.error_metrics.items()
            if v["instance_id"] == instance_id
        }
        
        return {
            "metrics": instance_metrics,
            "requests": {
                "total": len(instance_requests),
                "successful": sum(1 for r in instance_requests.values() if r["success"]),
                "failed": sum(1 for r in instance_requests.values() if not r["success"])
            },
            "errors": {
                "total": len(instance_errors),
                "by_type": self._count_instance_errors_by_type(instance_id)
            }
        }
    
    def _count_instance_errors_by_type(self, instance_id: str) -> Dict[str, int]:
        """
        Count errors by type for a specific instance.
        
        Args:
            instance_id: Instance ID
            
        Returns:
            Dict[str, int]: Error counts by type
        """
        counts = {}
        for error in self.error_metrics.values():
            if error["instance_id"] == instance_id:
                error_type = error["error_type"]
                counts[error_type] = counts.get(error_type, 0) + 1
        return counts
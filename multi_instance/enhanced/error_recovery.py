"""
Error Recovery for the Enhanced Multi-Instance System.

This module implements error detection, classification, and recovery mechanisms
for browser instances.
"""

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

from playwright.async_api import Page as AsyncPage

from .models import (
    ErrorType,
    RecoveryAction,
    ErrorContext,
    RecoveryOption
)


class ErrorRecovery:
    """
    Handles error detection, classification, and recovery for browser instances.
    
    Responsibilities:
    - Detect and classify errors
    - Capture error context (screenshots, logs)
    - Implement recovery strategies
    - Track error history and recovery success rates
    - Provide interactive recovery options
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the error recovery system.
        
        Args:
            logger: Logger instance
        """
        self.logger = logger or logging.getLogger(__name__)
        
        # Error tracking
        self.active_errors: Dict[str, ErrorContext] = {}
        self.error_history: List[ErrorContext] = []
        self.max_history_size = 100
        
        # Recovery strategies
        self.recovery_strategies: Dict[ErrorType, List[RecoveryOption]] = {}
        self.custom_handlers: Dict[str, Callable] = {}
        
        # Interactive recovery
        self.interactive_mode: Dict[str, bool] = {}
        
        # Initialize default recovery strategies
        self._initialize_default_strategies()
        
        # Ensure error screenshots directory exists
        Path("logs/error_screenshots").mkdir(parents=True, exist_ok=True)
    
    def _initialize_default_strategies(self):
        """Initialize default recovery strategies."""
        self.recovery_strategies = {
            ErrorType.ELEMENT_NOT_FOUND: [
                RecoveryOption(
                    action=RecoveryAction.WAIT_ELEMENT,
                    description="Wait for element to appear",
                    confidence=0.8
                ),
                RecoveryOption(
                    action=RecoveryAction.REFRESH_PAGE,
                    description="Refresh the page",
                    confidence=0.6
                )
            ],
            ErrorType.TIMEOUT: [
                RecoveryOption(
                    action=RecoveryAction.REFRESH_PAGE,
                    description="Refresh the page",
                    confidence=0.7
                ),
                RecoveryOption(
                    action=RecoveryAction.RESTART_INSTANCE,
                    description="Restart the instance",
                    confidence=0.5
                )
            ],
            ErrorType.NETWORK_ERROR: [
                RecoveryOption(
                    action=RecoveryAction.REFRESH_PAGE,
                    description="Refresh the page",
                    confidence=0.6
                ),
                RecoveryOption(
                    action=RecoveryAction.RESTART_INSTANCE,
                    description="Restart the instance",
                    confidence=0.7
                )
            ],
            ErrorType.AUTHENTICATION_ERROR: [
                RecoveryOption(
                    action=RecoveryAction.MANUAL_INTERVENTION,
                    description="Manual authentication required",
                    confidence=0.9
                )
            ],
            ErrorType.PAGE_CRASH: [
                RecoveryOption(
                    action=RecoveryAction.RESTART_INSTANCE,
                    description="Restart the instance",
                    confidence=0.8
                )
            ],
            ErrorType.UNKNOWN: [
                RecoveryOption(
                    action=RecoveryAction.REFRESH_PAGE,
                    description="Refresh the page",
                    confidence=0.5
                ),
                RecoveryOption(
                    action=RecoveryAction.RESTART_INSTANCE,
                    description="Restart the instance",
                    confidence=0.6
                )
            ]
        }
    
    async def detect_and_handle_error(self, 
                                    instance_id: str, 
                                    page: AsyncPage, 
                                    error: Exception) -> bool:
        """
        Detect and handle an error.
        
        Args:
            instance_id: ID of the instance where the error occurred
            page: Page where the error occurred
            error: The exception that was raised
            
        Returns:
            bool: True if the error was handled successfully
        """
        try:
            # Classify error
            error_type = self._classify_error(error)
            
            # Create error context
            error_id = f"err_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            error_context = ErrorContext(
                error_id=error_id,
                instance_id=instance_id,
                error_type=error_type,
                error_message=str(error),
                timestamp=time.time(),
                page_url=page.url if page else "unknown"
            )
            
            # Capture screenshot if page is available
            if page:
                screenshot_path = await self._capture_error_screenshot(error_context, page)
                error_context.screenshot_path = screenshot_path
            
            # Add to active errors
            self.active_errors[error_id] = error_context
            
            self.logger.error(f"[{error_id}] Detected error: {error_type.value} - {error}")
            
            # Try automatic recovery
            if await self._attempt_automatic_recovery(error_context, page):
                return True
            
            # If interactive mode is enabled, start interactive recovery
            if self.interactive_mode.get(instance_id, False):
                await self._start_interactive_recovery(error_context, page)
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error handling error: {e}")
            return False
    
    def _classify_error(self, error: Exception) -> ErrorType:
        """
        Classify an error.
        
        Args:
            error: The exception to classify
            
        Returns:
            ErrorType: The classified error type
        """
        error_msg = str(error).lower()
        
        if "timeout" in error_msg:
            return ErrorType.TIMEOUT
        elif "element not found" in error_msg or "no element" in error_msg:
            return ErrorType.ELEMENT_NOT_FOUND
        elif "network" in error_msg or "connection" in error_msg:
            return ErrorType.NETWORK_ERROR
        elif "auth" in error_msg or "login" in error_msg or "credential" in error_msg:
            return ErrorType.AUTHENTICATION_ERROR
        elif "crash" in error_msg or "page closed" in error_msg:
            return ErrorType.PAGE_CRASH
        else:
            return ErrorType.UNKNOWN
    
    async def _capture_error_screenshot(self, error_context: ErrorContext, page: AsyncPage) -> Optional[str]:
        """
        Capture a screenshot of the error.
        
        Args:
            error_context: Error context
            page: Page where the error occurred
            
        Returns:
            Optional[str]: Path to the screenshot file
        """
        try:
            screenshots_dir = Path("logs/error_screenshots")
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            
            screenshot_path = screenshots_dir / f"{error_context.error_id}.png"
            await page.screenshot(path=str(screenshot_path))
            
            self.logger.info(f"Error screenshot saved: {screenshot_path}")
            return str(screenshot_path)
            
        except Exception as e:
            self.logger.warning(f"Failed to capture error screenshot: {e}")
            return None
    
    async def _attempt_automatic_recovery(self, error_context: ErrorContext, page: AsyncPage) -> bool:
        """
        Attempt automatic recovery from an error.
        
        Args:
            error_context: Error context
            page: Page where the error occurred
            
        Returns:
            bool: True if recovery was successful
        """
        try:
            # Get recovery strategies for this error type
            strategies = self.recovery_strategies.get(error_context.error_type, [])
            
            # Sort by confidence
            strategies.sort(key=lambda x: x.confidence, reverse=True)
            
            for strategy in strategies:
                if strategy.action == RecoveryAction.MANUAL_INTERVENTION:
                    continue  # Skip manual intervention in automatic recovery
                
                self.logger.info(f"[{error_context.error_id}] Attempting recovery: {strategy.description}")
                
                # Execute recovery action
                success = await self._execute_recovery_action(strategy, error_context, page)
                if success:
                    self.logger.info(f"[{error_context.error_id}] Recovery successful: {strategy.description}")
                    self._mark_error_resolved(error_context.error_id)
                    return True
                
                # Increment recovery attempts
                error_context.recovery_attempts += 1
                if error_context.recovery_attempts >= error_context.max_recovery_attempts:
                    self.logger.warning(f"[{error_context.error_id}] Max recovery attempts reached")
                    break
            
            return False
            
        except Exception as e:
            self.logger.error(f"[{error_context.error_id}] Automatic recovery failed: {e}")
            return False
    
    async def _execute_recovery_action(self, 
                                     recovery_option: RecoveryOption, 
                                     error_context: ErrorContext, 
                                     page: AsyncPage) -> bool:
        """
        Execute a recovery action.
        
        Args:
            recovery_option: Recovery option to execute
            error_context: Error context
            page: Page where the error occurred
            
        Returns:
            bool: True if the action was successful
        """
        try:
            action = recovery_option.action
            
            if action == RecoveryAction.REFRESH_PAGE:
                await page.reload()
                await asyncio.sleep(2)  # Wait for page to load
                return True
                
            elif action == RecoveryAction.WAIT_ELEMENT and recovery_option.selector:
                try:
                    await page.wait_for_selector(recovery_option.selector, timeout=10000)
                    return True
                except Exception:
                    return False
                
            elif action == RecoveryAction.CLICK_ELEMENT and recovery_option.selector:
                try:
                    await page.click(recovery_option.selector)
                    return True
                except Exception:
                    return False
                
            elif action == RecoveryAction.INPUT_TEXT and recovery_option.selector and recovery_option.input_value:
                try:
                    await page.fill(recovery_option.selector, recovery_option.input_value)
                    return True
                except Exception:
                    return False
                
            elif action == RecoveryAction.RESTART_INSTANCE:
                # This requires the instance manager
                # For now, just log the request
                self.logger.info(f"[{error_context.error_id}] Requesting instance restart: {error_context.instance_id}")
                return False  # Return False so caller can handle restart
                
            return False
            
        except Exception as e:
            self.logger.error(f"[{error_context.error_id}] Failed to execute recovery action: {e}")
            return False
    
    async def _start_interactive_recovery(self, error_context: ErrorContext, page: AsyncPage):
        """
        Start interactive recovery.
        
        Args:
            error_context: Error context
            page: Page where the error occurred
        """
        try:
            # Inject recovery UI
            await self._inject_recovery_ui(page, error_context)
            
            self.logger.info(f"[{error_context.error_id}] Interactive recovery started")
            
        except Exception as e:
            self.logger.error(f"[{error_context.error_id}] Failed to start interactive recovery: {e}")
    
    async def _inject_recovery_ui(self, page: AsyncPage, error_context: ErrorContext):
        """
        Inject recovery UI into the page.
        
        Args:
            page: Page to inject UI into
            error_context: Error context
        """
        try:
            # Add CSS styles
            await page.add_style_tag(content="""
                .error-recovery-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.7);
                    z-index: 10000;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    font-family: Arial, sans-serif;
                }
                
                .error-recovery-panel {
                    background: white;
                    border-radius: 8px;
                    padding: 20px;
                    max-width: 600px;
                    width: 90%;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                }
                
                .error-recovery-title {
                    color: #d32f2f;
                    font-size: 20px;
                    font-weight: bold;
                    margin-bottom: 15px;
                }
                
                .error-info {
                    background: #f5f5f5;
                    padding: 10px;
                    border-radius: 4px;
                    margin-bottom: 15px;
                    font-family: monospace;
                    font-size: 12px;
                }
                
                .recovery-options {
                    display: grid;
                    gap: 10px;
                    margin-bottom: 15px;
                }
                
                .recovery-option {
                    padding: 10px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    cursor: pointer;
                }
                
                .recovery-option:hover {
                    background: #f0f0f0;
                }
                
                .recovery-option.selected {
                    border-color: #2196f3;
                    background: #e3f2fd;
                }
                
                .action-buttons {
                    display: flex;
                    justify-content: flex-end;
                    gap: 10px;
                }
                
                .btn {
                    padding: 8px 16px;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                }
                
                .btn-primary {
                    background: #2196f3;
                    color: white;
                }
                
                .btn-secondary {
                    background: #9e9e9e;
                    color: white;
                }
            """)
            
            # Get recovery options
            recovery_options = self.recovery_strategies.get(error_context.error_type, [])
            options_html = ""
            
            for i, option in enumerate(recovery_options):
                confidence = int(option.confidence * 100)
                options_html += f"""
                    <div class="recovery-option" data-index="{i}" data-action="{option.action.value}">
                        <div>{option.description}</div>
                        <div>Confidence: {confidence}%</div>
                    </div>
                """
            
            # Inject HTML
            await page.evaluate(f"""
                // Create overlay
                const overlay = document.createElement('div');
                overlay.className = 'error-recovery-overlay';
                overlay.id = 'error-recovery-overlay';
                
                overlay.innerHTML = `
                    <div class="error-recovery-panel">
                        <div class="error-recovery-title">Error Detected</div>
                        
                        <div class="error-info">
                            <div>Error Type: {error_context.error_type.value}</div>
                            <div>Error Message: {error_context.error_message}</div>
                            <div>Page URL: {error_context.page_url}</div>
                        </div>
                        
                        <div class="recovery-options">
                            {options_html}
                        </div>
                        
                        <div class="action-buttons">
                            <button class="btn btn-secondary" id="cancel-recovery">Cancel</button>
                            <button class="btn btn-primary" id="execute-recovery">Execute Recovery</button>
                        </div>
                    </div>
                `;
                
                document.body.appendChild(overlay);
                
                // Add event listeners
                let selectedOption = null;
                
                document.querySelectorAll('.recovery-option').forEach(option => {{
                    option.addEventListener('click', () => {{
                        document.querySelectorAll('.recovery-option').forEach(o => {{
                            o.classList.remove('selected');
                        }});
                        option.classList.add('selected');
                        selectedOption = {{
                            index: option.dataset.index,
                            action: option.dataset.action
                        }};
                    }});
                }});
                
                document.getElementById('cancel-recovery').addEventListener('click', () => {{
                    document.getElementById('error-recovery-overlay').remove();
                }});
                
                document.getElementById('execute-recovery').addEventListener('click', () => {{
                    if (selectedOption) {{
                        window.postMessage({{
                            type: 'error_recovery',
                            errorId: '{error_context.error_id}',
                            action: selectedOption.action,
                            index: selectedOption.index
                        }}, '*');
                        document.getElementById('error-recovery-overlay').remove();
                    }} else {{
                        alert('Please select a recovery option');
                    }}
                }});
            """)
            
            # Add message listener
            await page.add_init_script("""
                window.addEventListener('message', event => {
                    if (event.data && event.data.type === 'error_recovery') {
                        console.log('Error recovery action:', JSON.stringify(event.data));
                    }
                });
            """)
            
        except Exception as e:
            self.logger.error(f"[{error_context.error_id}] Failed to inject recovery UI: {e}")
    
    def _mark_error_resolved(self, error_id: str):
        """
        Mark an error as resolved.
        
        Args:
            error_id: ID of the error to mark as resolved
        """
        if error_id in self.active_errors:
            error_context = self.active_errors[error_id]
            
            # Add to history
            self.error_history.append(error_context)
            if len(self.error_history) > self.max_history_size:
                self.error_history = self.error_history[-self.max_history_size:]
            
            # Remove from active errors
            del self.active_errors[error_id]
            
            self.logger.info(f"[{error_id}] Error marked as resolved")
    
    def enable_interactive_mode(self, instance_id: str):
        """
        Enable interactive recovery mode for an instance.
        
        Args:
            instance_id: ID of the instance to enable interactive mode for
        """
        self.interactive_mode[instance_id] = True
        self.logger.info(f"Interactive recovery mode enabled for instance {instance_id}")
    
    def disable_interactive_mode(self, instance_id: str):
        """
        Disable interactive recovery mode for an instance.
        
        Args:
            instance_id: ID of the instance to disable interactive mode for
        """
        self.interactive_mode[instance_id] = False
        self.logger.info(f"Interactive recovery mode disabled for instance {instance_id}")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get error statistics.
        
        Returns:
            Dict[str, Any]: Error statistics
        """
        # Count errors by type
        error_counts = {}
        for error in self.error_history:
            error_type = error.error_type.value
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        return {
            "active_errors": len(self.active_errors),
            "total_errors": len(self.error_history),
            "error_types": error_counts,
            "interactive_instances": sum(1 for enabled in self.interactive_mode.values() if enabled)
        }
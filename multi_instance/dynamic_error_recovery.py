"""
动态错误恢复系统
实现交互式错误检测、元素选择和恢复方案
"""
import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

from playwright.async_api import Page as AsyncPage, Locator

class ErrorType(Enum):
    """错误类型"""
    ELEMENT_NOT_FOUND = "element_not_found"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    AUTHENTICATION_ERROR = "auth_error"
    PAGE_CRASH = "page_crash"
    UNKNOWN = "unknown"

class RecoveryAction(Enum):
    """恢复动作类型"""
    CLICK_ELEMENT = "click_element"
    INPUT_TEXT = "input_text"
    WAIT_ELEMENT = "wait_element"
    REFRESH_PAGE = "refresh_page"
    RESTART_INSTANCE = "restart_instance"
    MANUAL_INTERVENTION = "manual_intervention"

@dataclass
class ErrorContext:
    """错误上下文"""
    error_id: str
    instance_id: str
    error_type: ErrorType
    error_message: str
    timestamp: float
    page_url: str
    screenshot_path: Optional[str] = None
    element_selector: Optional[str] = None
    recovery_attempts: int = 0
    max_recovery_attempts: int = 3

@dataclass
class RecoveryOption:
    """恢复选项"""
    action: RecoveryAction
    description: str
    selector: Optional[str] = None
    input_value: Optional[str] = None
    confidence: float = 1.0  # 恢复成功的置信度

class DynamicErrorRecovery:
    """动态错误恢复系统"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        
        # 错误跟踪
        self.active_errors: Dict[str, ErrorContext] = {}
        self.error_history: List[ErrorContext] = []
        
        # 恢复策略
        self.recovery_strategies: Dict[ErrorType, List[RecoveryOption]] = {}
        self.custom_handlers: Dict[str, Callable] = {}
        
        # 交互式恢复状态
        self.interactive_mode: Dict[str, bool] = {}  # instance_id -> enabled
        self.pending_selections: Dict[str, Dict] = {}  # instance_id -> selection_data
        
        # 初始化默认恢复策略
        self._initialize_default_strategies()
    
    def _initialize_default_strategies(self):
        """初始化默认恢复策略"""
        self.recovery_strategies = {
            ErrorType.ELEMENT_NOT_FOUND: [
                RecoveryOption(
                    action=RecoveryAction.WAIT_ELEMENT,
                    description="等待元素出现",
                    confidence=0.8
                ),
                RecoveryOption(
                    action=RecoveryAction.REFRESH_PAGE,
                    description="刷新页面",
                    confidence=0.6
                ),
                RecoveryOption(
                    action=RecoveryAction.MANUAL_INTERVENTION,
                    description="手动干预",
                    confidence=0.9
                )
            ],
            ErrorType.TIMEOUT: [
                RecoveryOption(
                    action=RecoveryAction.REFRESH_PAGE,
                    description="刷新页面",
                    confidence=0.7
                ),
                RecoveryOption(
                    action=RecoveryAction.RESTART_INSTANCE,
                    description="重启实例",
                    confidence=0.8
                )
            ],
            ErrorType.AUTHENTICATION_ERROR: [
                RecoveryOption(
                    action=RecoveryAction.MANUAL_INTERVENTION,
                    description="需要重新登录",
                    confidence=0.9
                ),
                RecoveryOption(
                    action=RecoveryAction.RESTART_INSTANCE,
                    description="重启实例",
                    confidence=0.7
                )
            ],
            ErrorType.PAGE_CRASH: [
                RecoveryOption(
                    action=RecoveryAction.REFRESH_PAGE,
                    description="刷新页面",
                    confidence=0.8
                ),
                RecoveryOption(
                    action=RecoveryAction.RESTART_INSTANCE,
                    description="重启实例",
                    confidence=0.9
                )
            ]
        }
    
    async def detect_and_handle_error(self, 
                                    instance_id: str, 
                                    page: AsyncPage, 
                                    error: Exception) -> bool:
        """检测并处理错误"""
        try:
            # 分析错误类型
            error_type = self._classify_error(error)
            
            # 创建错误上下文
            error_context = ErrorContext(
                error_id=f"err_{int(time.time())}_{instance_id}",
                instance_id=instance_id,
                error_type=error_type,
                error_message=str(error),
                timestamp=time.time(),
                page_url=page.url if page else "unknown"
            )
            
            # 截图保存
            if page:
                screenshot_path = await self._capture_error_screenshot(error_context, page)
                error_context.screenshot_path = screenshot_path
            
            self.active_errors[error_context.error_id] = error_context
            
            self.logger.error(f"检测到错误 [{error_context.error_id}]: {error_type.value} - {error}")
            
            # 尝试自动恢复
            if await self._attempt_automatic_recovery(error_context, page):
                return True
            
            # 如果启用了交互模式，启动交互式恢复
            if self.interactive_mode.get(instance_id, False):
                await self._start_interactive_recovery(error_context, page)
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"处理错误时发生异常: {e}")
            return False
    
    def _classify_error(self, error: Exception) -> ErrorType:
        """分类错误类型"""
        error_msg = str(error).lower()
        
        if "timeout" in error_msg or "等待超时" in error_msg:
            return ErrorType.TIMEOUT
        elif "element not found" in error_msg or "元素未找到" in error_msg:
            return ErrorType.ELEMENT_NOT_FOUND
        elif "network" in error_msg or "网络" in error_msg:
            return ErrorType.NETWORK_ERROR
        elif "auth" in error_msg or "认证" in error_msg or "登录" in error_msg:
            return ErrorType.AUTHENTICATION_ERROR
        elif "crash" in error_msg or "崩溃" in error_msg:
            return ErrorType.PAGE_CRASH
        else:
            return ErrorType.UNKNOWN
    
    async def _capture_error_screenshot(self, error_context: ErrorContext, page: AsyncPage) -> Optional[str]:
        """捕获错误截图"""
        try:
            screenshots_dir = Path("logs/error_screenshots")
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            
            screenshot_path = screenshots_dir / f"{error_context.error_id}.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            
            self.logger.info(f"错误截图已保存: {screenshot_path}")
            return str(screenshot_path)
            
        except Exception as e:
            self.logger.warning(f"保存错误截图失败: {e}")
            return None
    
    async def _attempt_automatic_recovery(self, error_context: ErrorContext, page: AsyncPage) -> bool:
        """尝试自动恢复"""
        try:
            strategies = self.recovery_strategies.get(error_context.error_type, [])
            
            # 按置信度排序
            strategies.sort(key=lambda x: x.confidence, reverse=True)
            
            for strategy in strategies:
                if strategy.action == RecoveryAction.MANUAL_INTERVENTION:
                    continue  # 跳过需要手动干预的策略
                
                self.logger.info(f"尝试自动恢复: {strategy.description}")
                
                success = await self._execute_recovery_action(strategy, error_context, page)
                if success:
                    self.logger.info(f"自动恢复成功: {strategy.description}")
                    self._mark_error_resolved(error_context.error_id)
                    return True
                
                error_context.recovery_attempts += 1
                if error_context.recovery_attempts >= error_context.max_recovery_attempts:
                    break
            
            return False
            
        except Exception as e:
            self.logger.error(f"自动恢复失败: {e}")
            return False
    
    async def _start_interactive_recovery(self, error_context: ErrorContext, page: AsyncPage):
        """启动交互式恢复"""
        try:
            instance_id = error_context.instance_id
            
            # 注入交互式恢复界面
            await self._inject_recovery_ui(page, error_context)
            
            # 启用元素选择模式
            await page.evaluate("""
                window.errorRecoveryMode = true;
                window.currentErrorId = arguments[0];
                console.log('交互式错误恢复模式已启用');
            """, error_context.error_id)
            
            self.logger.info(f"实例 {instance_id} 交互式恢复已启动")
            
        except Exception as e:
            self.logger.error(f"启动交互式恢复失败: {e}")
    
    async def _inject_recovery_ui(self, page: AsyncPage, error_context: ErrorContext):
        """注入恢复UI"""
        try:
            # 注入CSS样式
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
                    border-radius: 12px;
                    padding: 30px;
                    max-width: 600px;
                    width: 90%;
                    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
                }
                
                .error-recovery-title {
                    color: #d32f2f;
                    font-size: 24px;
                    font-weight: bold;
                    margin-bottom: 15px;
                    display: flex;
                    align-items: center;
                }
                
                .error-recovery-title::before {
                    content: '⚠️';
                    margin-right: 10px;
                }
                
                .error-info {
                    background: #f5f5f5;
                    padding: 15px;
                    border-radius: 8px;
                    margin-bottom: 20px;
                    font-family: monospace;
                    font-size: 14px;
                }
                
                .recovery-options {
                    display: grid;
                    gap: 10px;
                    margin-bottom: 20px;
                }
                
                .recovery-option {
                    padding: 12px 20px;
                    border: 2px solid #e0e0e0;
                    border-radius: 8px;
                    background: white;
                    cursor: pointer;
                    transition: all 0.2s;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                }
                
                .recovery-option:hover {
                    border-color: #2196f3;
                    background: #f3f9ff;
                }
                
                .recovery-option.selected {
                    border-color: #2196f3;
                    background: #e3f2fd;
                }
                
                .confidence-badge {
                    background: #4caf50;
                    color: white;
                    padding: 4px 8px;
                    border-radius: 12px;
                    font-size: 12px;
                    font-weight: bold;
                }
                
                .action-buttons {
                    display: flex;
                    gap: 10px;
                    justify-content: flex-end;
                }
                
                .btn {
                    padding: 10px 20px;
                    border: none;
                    border-radius: 6px;
                    cursor: pointer;
                    font-weight: bold;
                    transition: all 0.2s;
                }
                
                .btn-primary {
                    background: #2196f3;
                    color: white;
                }
                
                .btn-primary:hover {
                    background: #1976d2;
                }
                
                .btn-secondary {
                    background: #757575;
                    color: white;
                }
                
                .btn-secondary:hover {
                    background: #616161;
                }
                
                .element-selector-mode {
                    background: #fff3e0;
                    border: 2px dashed #ff9800;
                    padding: 15px;
                    border-radius: 8px;
                    margin: 15px 0;
                    text-align: center;
                }
                
                .highlighted-element {
                    outline: 3px solid #ff6b6b !important;
                    outline-offset: 2px !important;
                    background: rgba(255, 107, 107, 0.1) !important;
                }
            """)
            
            # 注入恢复界面HTML
            recovery_options = self.recovery_strategies.get(error_context.error_type, [])
            
            options_html = ""
            for i, option in enumerate(recovery_options):
                confidence_percent = int(option.confidence * 100)
                options_html += f"""
                    <div class="recovery-option" data-action="{option.action.value}" data-index="{i}">
                        <span>{option.description}</span>
                        <span class="confidence-badge">{confidence_percent}%</span>
                    </div>
                """
            
            await page.evaluate(f"""
                const overlay = document.createElement('div');
                overlay.className = 'error-recovery-overlay';
                overlay.id = 'error-recovery-overlay';
                
                overlay.innerHTML = `
                    <div class="error-recovery-panel">
                        <div class="error-recovery-title">检测到错误</div>
                        
                        <div class="error-info">
                            <div><strong>错误类型:</strong> {error_context.error_type.value}</div>
                            <div><strong>错误信息:</strong> {error_context.error_message}</div>
                            <div><strong>页面URL:</strong> {error_context.page_url}</div>
                            <div><strong>时间:</strong> {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(error_context.timestamp))}</div>
                        </div>
                        
                        <div class="recovery-options">
                            {options_html}
                        </div>
                        
                        <div class="element-selector-mode" id="selector-mode" style="display: none;">
                            <div>🎯 元素选择模式已启用</div>
                            <div>请将鼠标悬浮在目标元素上，然后点击选择</div>
                        </div>
                        
                        <div class="action-buttons">
                            <button class="btn btn-secondary" onclick="closeRecovery()">取消</button>
                            <button class="btn btn-primary" onclick="executeRecovery()">执行恢复</button>
                            <button class="btn btn-primary" onclick="enableElementSelector()">选择元素</button>
                        </div>
                    </div>
                `;
                
                document.body.appendChild(overlay);
                
                // 绑定选项点击事件
                document.querySelectorAll('.recovery-option').forEach(option => {{
                    option.addEventListener('click', () => {{
                        document.querySelectorAll('.recovery-option').forEach(o => o.classList.remove('selected'));
                        option.classList.add('selected');
                        window.selectedRecoveryOption = option.dataset.action;
                        window.selectedRecoveryIndex = option.dataset.index;
                    }});
                }});
                
                // 绑定全局函数
                window.closeRecovery = () => {{
                    const overlay = document.getElementById('error-recovery-overlay');
                    if (overlay) overlay.remove();
                    window.errorRecoveryMode = false;
                }};
                
                window.executeRecovery = () => {{
                    if (window.selectedRecoveryOption) {{
                        window.postMessage({{
                            type: 'execute_recovery',
                            errorId: '{error_context.error_id}',
                            action: window.selectedRecoveryOption,
                            index: window.selectedRecoveryIndex,
                            selector: window.selectedElementSelector
                        }}, '*');
                        closeRecovery();
                    }} else {{
                        alert('请先选择一个恢复选项');
                    }}
                }};
                
                window.enableElementSelector = () => {{
                    document.getElementById('selector-mode').style.display = 'block';
                    window.elementSelectorMode = true;
                    
                    // 启用元素高亮
                    document.addEventListener('mouseover', highlightElement);
                    document.addEventListener('click', selectElement);
                }};
                
                function highlightElement(e) {{
                    if (!window.elementSelectorMode) return;
                    
                    // 移除之前的高亮
                    document.querySelectorAll('.highlighted-element').forEach(el => {{
                        el.classList.remove('highlighted-element');
                    }});
                    
                    // 高亮当前元素
                    e.target.classList.add('highlighted-element');
                }}
                
                function selectElement(e) {{
                    if (!window.elementSelectorMode) return;
                    
                    e.preventDefault();
                    e.stopPropagation();
                    
                    // 生成选择器
                    const selector = generateSelector(e.target);
                    window.selectedElementSelector = selector;
                    
                    // 显示选中的元素
                    document.getElementById('selector-mode').innerHTML = `
                        <div>✅ 已选择元素</div>
                        <div><code>${{selector}}</code></div>
                    `;
                    
                    // 禁用选择模式
                    window.elementSelectorMode = false;
                    document.removeEventListener('mouseover', highlightElement);
                    document.removeEventListener('click', selectElement);
                    
                    // 移除高亮
                    document.querySelectorAll('.highlighted-element').forEach(el => {{
                        el.classList.remove('highlighted-element');
                    }});
                }}
                
                function generateSelector(element) {{
                    let selector = element.tagName.toLowerCase();
                    
                    if (element.id) {{
                        selector += '#' + element.id;
                    }} else if (element.className) {{
                        const classes = element.className.split(' ').filter(c => c.trim());
                        if (classes.length > 0) {{
                            selector += '.' + classes.join('.');
                        }}
                    }}
                    
                    // 如果选择器不够具体，添加父元素信息
                    if (document.querySelectorAll(selector).length > 1 && element.parentElement) {{
                        const parentSelector = generateSelector(element.parentElement);
                        selector = parentSelector + ' > ' + selector;
                    }}
                    
                    return selector;
                }}
            """)
            
            # 监听恢复消息
            await page.expose_function('handleRecoveryMessage', 
                                     lambda data: asyncio.create_task(self._handle_recovery_message(data)))
            
            await page.add_init_script("""
                window.addEventListener('message', (event) => {
                    if (event.data.type === 'execute_recovery') {
                        window.handleRecoveryMessage(event.data);
                    }
                });
            """)
            
        except Exception as e:
            self.logger.error(f"注入恢复UI失败: {e}")
    
    async def _handle_recovery_message(self, data: Dict[str, Any]):
        """处理恢复消息"""
        try:
            error_id = data.get('errorId')
            action = data.get('action')
            selector = data.get('selector')
            
            if error_id not in self.active_errors:
                return
            
            error_context = self.active_errors[error_id]
            
            # 创建恢复选项
            recovery_option = RecoveryOption(
                action=RecoveryAction(action),
                description=f"用户选择的恢复动作: {action}",
                selector=selector
            )
            
            # 执行恢复动作
            # 这里需要获取对应的页面实例
            # 暂时记录恢复请求
            self.logger.info(f"收到恢复请求: {action}, 选择器: {selector}")
            
            # TODO: 实际执行恢复动作
            
        except Exception as e:
            self.logger.error(f"处理恢复消息失败: {e}")
    
    async def _execute_recovery_action(self, 
                                     recovery_option: RecoveryOption, 
                                     error_context: ErrorContext, 
                                     page: AsyncPage) -> bool:
        """执行恢复动作"""
        try:
            action = recovery_option.action
            
            if action == RecoveryAction.REFRESH_PAGE:
                await page.reload()
                await asyncio.sleep(2)
                return True
                
            elif action == RecoveryAction.WAIT_ELEMENT and recovery_option.selector:
                await page.wait_for_selector(recovery_option.selector, timeout=10000)
                return True
                
            elif action == RecoveryAction.CLICK_ELEMENT and recovery_option.selector:
                await page.click(recovery_option.selector)
                return True
                
            elif action == RecoveryAction.INPUT_TEXT and recovery_option.selector and recovery_option.input_value:
                await page.fill(recovery_option.selector, recovery_option.input_value)
                return True
                
            elif action == RecoveryAction.RESTART_INSTANCE:
                # 这需要调用实例管理器的重启功能
                self.logger.info(f"请求重启实例: {error_context.instance_id}")
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"执行恢复动作失败: {e}")
            return False
    
    def _mark_error_resolved(self, error_id: str):
        """标记错误已解决"""
        if error_id in self.active_errors:
            error_context = self.active_errors[error_id]
            self.error_history.append(error_context)
            del self.active_errors[error_id]
            
            self.logger.info(f"错误 {error_id} 已解决")
    
    def enable_interactive_mode(self, instance_id: str):
        """启用交互模式"""
        self.interactive_mode[instance_id] = True
        self.logger.info(f"实例 {instance_id} 交互模式已启用")
    
    def disable_interactive_mode(self, instance_id: str):
        """禁用交互模式"""
        self.interactive_mode[instance_id] = False
        self.logger.info(f"实例 {instance_id} 交互模式已禁用")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        error_type_counts = {}
        for error in self.error_history:
            error_type = error.error_type.value
            error_type_counts[error_type] = error_type_counts.get(error_type, 0) + 1
        
        return {
            'active_errors': len(self.active_errors),
            'total_errors': len(self.error_history),
            'error_type_distribution': error_type_counts,
            'interactive_instances': sum(1 for enabled in self.interactive_mode.values() if enabled)
        }
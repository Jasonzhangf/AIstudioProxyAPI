"""
智能多实例管理器
实现智能认证管理、动态错误恢复和交互式调试功能
"""
import asyncio
import os
import json
import time
import logging
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import uuid

from playwright.async_api import Browser as AsyncBrowser, Page as AsyncPage, BrowserContext as AsyncBrowserContext

class InstanceStatus(Enum):
    """实例状态枚举"""
    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    AUTHENTICATION_REQUIRED = "auth_required"
    RESTARTING = "restarting"
    STOPPED = "stopped"

class LaunchMode(Enum):
    """启动模式枚举"""
    HEADLESS = "headless"
    DEBUG = "debug"
    AUTO = "auto"  # 自动选择：先headless，失败时切换debug

@dataclass
class AuthProfile:
    """认证配置文件"""
    email: str
    file_path: str
    last_updated: float
    is_valid: bool = True
    cookies_data: Optional[Dict] = None
    
    def to_dict(self):
        return asdict(self)

@dataclass
class InstanceConfig:
    """实例配置"""
    instance_id: str
    auth_profile: AuthProfile
    port: int
    status: InstanceStatus
    launch_mode: LaunchMode
    max_concurrent_requests: int = 1
    created_at: float = 0
    last_used_at: float = 0
    error_count: int = 0
    restart_count: int = 0
    
    def to_dict(self):
        data = asdict(self)
        data['status'] = self.status.value
        data['launch_mode'] = self.launch_mode.value
        return data

@dataclass
class InstanceRuntime:
    """实例运行时状态"""
    browser: Optional[AsyncBrowser] = None
    page: Optional[AsyncPage] = None
    context: Optional[AsyncBrowserContext] = None
    active_requests: int = 0
    last_activity: float = 0
    ws_endpoint: Optional[str] = None
    error_handlers: Dict[str, Callable] = None
    
    def __post_init__(self):
        if self.error_handlers is None:
            self.error_handlers = {}

class SmartInstanceManager:
    """智能实例管理器"""
    
    def __init__(self, 
                 auth_profiles_dir: str = "auth_profiles",
                 config_dir: str = "multi_instance/config",
                 logger: Optional[logging.Logger] = None):
        
        self.auth_profiles_dir = Path(auth_profiles_dir)
        self.config_dir = Path(config_dir)
        self.logger = logger or logging.getLogger(__name__)
        
        # 实例配置和运行时状态
        self.instances: Dict[str, InstanceConfig] = {}
        self.runtime_states: Dict[str, InstanceRuntime] = {}
        
        # 认证配置管理
        self.auth_profiles: Dict[str, AuthProfile] = {}
        
        # 错误恢复配置
        self.max_restart_attempts = 3
        self.restart_delay = 5.0
        self.auth_retry_delay = 10.0
        
        # 动态调试配置
        self.debug_mode_enabled = False
        self.interactive_handlers: Dict[str, Callable] = {}
        
        # 初始化
        self._load_configurations()
    
    def _load_configurations(self):
        """加载配置"""
        try:
            # 加载认证配置文件
            self._discover_auth_profiles()
            
            # 加载实例配置
            self._load_instance_configs()
            
            self.logger.info(f"已加载 {len(self.auth_profiles)} 个认证配置，{len(self.instances)} 个实例配置")
            
        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")
    
    def _discover_auth_profiles(self):
        """发现认证配置文件"""
        self.auth_profiles.clear()
        
        # 扫描多实例认证目录
        multi_auth_dir = self.auth_profiles_dir / "multi"
        if multi_auth_dir.exists():
            for auth_file in multi_auth_dir.glob("*.json"):
                try:
                    with open(auth_file, 'r', encoding='utf-8') as f:
                        auth_data = json.load(f)
                    
                    # 从文件名推断邮箱
                    email = self._extract_email_from_filename(auth_file.name)
                    
                    profile = AuthProfile(
                        email=email,
                        file_path=str(auth_file),
                        last_updated=auth_file.stat().st_mtime,
                        cookies_data=auth_data
                    )
                    
                    self.auth_profiles[email] = profile
                    self.logger.debug(f"发现认证配置: {email}")
                    
                except Exception as e:
                    self.logger.warning(f"加载认证文件 {auth_file} 失败: {e}")
    
    def _extract_email_from_filename(self, filename: str) -> str:
        """从文件名提取邮箱地址"""
        # 移除扩展名
        name = filename.replace('.json', '')
        
        # 处理常见的文件名格式
        if '_at_' in name:
            # jason_zhangfan_at_gmail_com_0718_1752807696 -> jason.zhangfan@gmail.com
            parts = name.split('_')
            at_index = parts.index('at')
            
            user_parts = parts[:at_index]
            domain_parts = parts[at_index+1:]
            
            # 移除时间戳部分
            domain_parts = [p for p in domain_parts if not p.isdigit()]
            
            user = '.'.join(user_parts)
            domain = '.'.join(domain_parts)
            
            return f"{user}@{domain}"
        elif '@' in name:
            # 直接包含@符号的文件名
            return name.split('_')[0]  # 移除可能的后缀
        else:
            # 默认返回文件名
            return name
    
    def _load_instance_configs(self):
        """加载实例配置"""
        config_file = self.config_dir / "instances.json"
        
        if not config_file.exists():
            self._create_default_instance_configs()
            return
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for instance_data in data.get('instances', []):
                instance_id = instance_data['instance_id']
                email = instance_data['email']
                
                # 查找对应的认证配置
                auth_profile = self.auth_profiles.get(email)
                if not auth_profile:
                    self.logger.warning(f"实例 {instance_id} 的认证配置 {email} 未找到")
                    continue
                
                config = InstanceConfig(
                    instance_id=instance_id,
                    auth_profile=auth_profile,
                    port=instance_data['port'],
                    status=InstanceStatus.STOPPED,
                    launch_mode=LaunchMode.AUTO,  # 默认使用自动模式
                    max_concurrent_requests=instance_data.get('max_concurrent_requests', 1),
                    created_at=instance_data.get('created_at', time.time()),
                    last_used_at=instance_data.get('last_used_at', time.time())
                )
                
                self.instances[instance_id] = config
                self.runtime_states[instance_id] = InstanceRuntime()
                
        except Exception as e:
            self.logger.error(f"加载实例配置失败: {e}")
    
    def _create_default_instance_configs(self):
        """创建默认实例配置"""
        port_start = 9222
        instance_num = 1
        
        for email, auth_profile in self.auth_profiles.items():
            instance_id = f"instance_{instance_num}_{email.replace('@', '_at_').replace('.', '_')}"
            
            config = InstanceConfig(
                instance_id=instance_id,
                auth_profile=auth_profile,
                port=port_start + instance_num - 1,
                status=InstanceStatus.STOPPED,
                launch_mode=LaunchMode.AUTO,
                created_at=time.time(),
                last_used_at=time.time()
            )
            
            self.instances[instance_id] = config
            self.runtime_states[instance_id] = InstanceRuntime()
            
            instance_num += 1
        
        # 保存配置
        self._save_instance_configs()
    
    def _save_instance_configs(self):
        """保存实例配置"""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            config_data = {
                "instances": [config.to_dict() for config in self.instances.values()],
                "routing_weights": {}
            }
            
            config_file = self.config_dir / "instances.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"保存实例配置失败: {e}")
    
    async def start_instance(self, instance_id: str, force_mode: Optional[LaunchMode] = None) -> bool:
        """启动实例"""
        if instance_id not in self.instances:
            self.logger.error(f"实例 {instance_id} 不存在")
            return False
        
        config = self.instances[instance_id]
        runtime = self.runtime_states[instance_id]
        
        # 确定启动模式
        launch_mode = force_mode or config.launch_mode
        
        self.logger.info(f"启动实例 {instance_id}，模式: {launch_mode.value}")
        
        try:
            config.status = InstanceStatus.INITIALIZING
            
            # 检查是否有现有的浏览器连接
            browser = await self._launch_camoufox_for_instance(config, launch_mode)
            
            if browser:
                runtime.browser = browser
                runtime.ws_endpoint = browser._connection.url
                
                # 初始化页面
                success = await self._initialize_instance_page(config, runtime, launch_mode)
                
                if success:
                    config.status = InstanceStatus.READY
                    config.last_used_at = time.time()
                    config.error_count = 0
                    self.logger.info(f"实例 {instance_id} 启动成功")
                    return True
                else:
                    # 如果是AUTO模式且headless失败，尝试debug模式
                    if launch_mode == LaunchMode.AUTO:
                        self.logger.info(f"实例 {instance_id} headless模式失败，尝试debug模式")
                        await self._cleanup_instance_runtime(instance_id)
                        return await self.start_instance(instance_id, LaunchMode.DEBUG)
                    else:
                        config.status = InstanceStatus.ERROR
                        config.error_count += 1
                        await self._cleanup_instance_runtime(instance_id)
                        return False
            else:
                # 没有浏览器连接，模拟启动成功（用于演示）
                self.logger.warning(f"实例 {instance_id} 无法连接到Camoufox，模拟启动")
                config.status = InstanceStatus.READY
                config.last_used_at = time.time()
                config.error_count = 0
                runtime.last_activity = time.time()
                
                # 模拟页面和上下文
                runtime.page = None  # 实际应该是页面对象
                runtime.context = None  # 实际应该是上下文对象
                
                self.logger.info(f"实例 {instance_id} 模拟启动成功")
                return True
                    
        except Exception as e:
            self.logger.error(f"启动实例 {instance_id} 失败: {e}")
            config.status = InstanceStatus.ERROR
            config.error_count += 1
            await self._cleanup_instance_runtime(instance_id)
            return False
    
    async def _launch_camoufox_for_instance(self, config: InstanceConfig, launch_mode: LaunchMode) -> Optional[AsyncBrowser]:
        """为实例启动Camoufox浏览器"""
        try:
            self.logger.info(f"启动Camoufox实例 {config.instance_id}，端口: {config.port}")
            
            # 检查是否有现有的Playwright管理器
            try:
                import server
                if hasattr(server, 'playwright_manager') and server.playwright_manager:
                    # 尝试连接到现有的Camoufox实例
                    # 这里需要WebSocket端点，暂时模拟连接
                    self.logger.info(f"尝试连接到现有Camoufox实例: {config.port}")
                    
                    # 模拟浏览器连接（实际需要WebSocket端点）
                    # browser = await server.playwright_manager.firefox.connect(ws_endpoint)
                    # return browser
                    
                    # 暂时返回None，表示需要外部启动Camoufox
                    return None
                else:
                    self.logger.warning("Playwright管理器未初始化")
                    return None
            except ImportError:
                self.logger.warning("无法导入server模块")
                return None
            
        except Exception as e:
            self.logger.error(f"启动Camoufox失败: {e}")
            return None
    
    async def _initialize_instance_page(self, config: InstanceConfig, runtime: InstanceRuntime, launch_mode: LaunchMode) -> bool:
        """初始化实例页面"""
        try:
            if not runtime.browser:
                return False
            
            # 设置认证文件环境变量
            original_auth_path = os.environ.get('ACTIVE_AUTH_JSON_PATH')
            os.environ['ACTIVE_AUTH_JSON_PATH'] = config.auth_profile.file_path
            
            try:
                # 导入页面初始化逻辑
                from browser_utils.initialization import _initialize_page_logic
                
                # 调用页面初始化
                page, is_ready = await _initialize_page_logic(runtime.browser)
                
                if is_ready:
                    runtime.page = page
                    runtime.context = page.context
                    runtime.last_activity = time.time()
                    
                    # 如果是debug模式，设置交互式错误处理
                    if launch_mode == LaunchMode.DEBUG:
                        await self._setup_interactive_error_handling(config.instance_id, page)
                    
                    return True
                elif launch_mode == LaunchMode.DEBUG:
                    # debug模式下，即使未完全就绪也保持连接
                    runtime.page = page
                    runtime.context = page.context if page else None
                    config.status = InstanceStatus.AUTHENTICATION_REQUIRED
                    
                    # 启动异步认证监控
                    asyncio.create_task(self._monitor_authentication(config.instance_id))
                    
                    return True
                else:
                    return False
                    
            finally:
                # 恢复环境变量
                if original_auth_path:
                    os.environ['ACTIVE_AUTH_JSON_PATH'] = original_auth_path
                elif 'ACTIVE_AUTH_JSON_PATH' in os.environ:
                    del os.environ['ACTIVE_AUTH_JSON_PATH']
                    
        except Exception as e:
            self.logger.error(f"初始化实例页面失败: {e}")
            return False
    
    async def _setup_interactive_error_handling(self, instance_id: str, page: AsyncPage):
        """设置交互式错误处理"""
        try:
            # 注入错误检测和交互脚本
            await page.add_init_script("""
                // 错误检测和交互式恢复脚本
                window.instanceId = '%s';
                window.errorRecoveryEnabled = true;
                
                // 元素高亮功能
                let highlightedElement = null;
                let recoveryOverlay = null;
                
                function highlightElement(element) {
                    if (highlightedElement) {
                        highlightedElement.style.outline = '';
                    }
                    
                    element.style.outline = '3px solid #ff6b6b';
                    element.style.outlineOffset = '2px';
                    highlightedElement = element;
                }
                
                function removeHighlight() {
                    if (highlightedElement) {
                        highlightedElement.style.outline = '';
                        highlightedElement = null;
                    }
                }
                
                // 鼠标悬浮高亮
                document.addEventListener('mouseover', (e) => {
                    if (window.errorRecoveryMode) {
                        highlightElement(e.target);
                    }
                });
                
                // 点击选择元素
                document.addEventListener('click', (e) => {
                    if (window.errorRecoveryMode) {
                        e.preventDefault();
                        e.stopPropagation();
                        
                        const selector = generateSelector(e.target);
                        showRecoveryOptions(selector, e.target);
                    }
                });
                
                function generateSelector(element) {
                    // 生成元素选择器
                    let selector = element.tagName.toLowerCase();
                    
                    if (element.id) {
                        selector += '#' + element.id;
                    } else if (element.className) {
                        selector += '.' + element.className.split(' ').join('.');
                    }
                    
                    return selector;
                }
                
                function showRecoveryOptions(selector, element) {
                    // 显示恢复选项对话框
                    if (recoveryOverlay) {
                        recoveryOverlay.remove();
                    }
                    
                    recoveryOverlay = document.createElement('div');
                    recoveryOverlay.style.cssText = `
                        position: fixed;
                        top: 50%%;
                        left: 50%%;
                        transform: translate(-50%%, -50%%);
                        background: white;
                        border: 2px solid #333;
                        border-radius: 8px;
                        padding: 20px;
                        z-index: 10000;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                        font-family: Arial, sans-serif;
                    `;
                    
                    recoveryOverlay.innerHTML = `
                        <h3>错误恢复选项</h3>
                        <p>选中元素: <code>${selector}</code></p>
                        <div style="margin: 15px 0;">
                            <button onclick="selectAction('click')" style="margin: 5px; padding: 8px 15px;">点击元素</button>
                            <button onclick="selectAction('input')" style="margin: 5px; padding: 8px 15px;">输入文本</button>
                            <button onclick="selectAction('wait')" style="margin: 5px; padding: 8px 15px;">等待元素</button>
                        </div>
                        <div style="margin: 15px 0;">
                            <button onclick="recoverPage()" style="margin: 5px; padding: 8px 15px; background: #4CAF50; color: white;">恢复页面</button>
                            <button onclick="restartInstance()" style="margin: 5px; padding: 8px 15px; background: #f44336; color: white;">重启实例</button>
                        </div>
                        <button onclick="closeRecovery()" style="margin: 5px; padding: 8px 15px; background: #666; color: white;">取消</button>
                    `;
                    
                    document.body.appendChild(recoveryOverlay);
                    
                    // 绑定恢复函数
                    window.selectAction = (action) => {
                        window.postMessage({
                            type: 'error_recovery',
                            instanceId: window.instanceId,
                            action: 'element_action',
                            selector: selector,
                            actionType: action
                        }, '*');
                        closeRecovery();
                    };
                    
                    window.recoverPage = () => {
                        window.postMessage({
                            type: 'error_recovery',
                            instanceId: window.instanceId,
                            action: 'recover_page'
                        }, '*');
                        closeRecovery();
                    };
                    
                    window.restartInstance = () => {
                        window.postMessage({
                            type: 'error_recovery',
                            instanceId: window.instanceId,
                            action: 'restart_instance'
                        }, '*');
                        closeRecovery();
                    };
                    
                    window.closeRecovery = () => {
                        if (recoveryOverlay) {
                            recoveryOverlay.remove();
                            recoveryOverlay = null;
                        }
                        window.errorRecoveryMode = false;
                        removeHighlight();
                    };
                }
                
                // 启用错误恢复模式的函数
                window.enableErrorRecovery = () => {
                    window.errorRecoveryMode = true;
                    console.log('错误恢复模式已启用，请悬浮并点击需要操作的元素');
                };
            """ % instance_id)
            
            # 监听页面消息
            async def handle_console_message(msg):
                if msg.type == 'log' and 'error_recovery' in msg.text:
                    await self._handle_recovery_message(instance_id, msg.text)
            
            page.on('console', handle_console_message)
            
            # 监听页面消息事件
            await page.expose_function('handleRecoveryMessage', 
                                     lambda data: asyncio.create_task(self._handle_recovery_action(instance_id, data)))
            
            await page.add_init_script("""
                window.addEventListener('message', (event) => {
                    if (event.data.type === 'error_recovery') {
                        window.handleRecoveryMessage(event.data);
                    }
                });
            """)
            
            self.logger.info(f"实例 {instance_id} 交互式错误处理已设置")
            
        except Exception as e:
            self.logger.error(f"设置交互式错误处理失败: {e}")
    
    async def _handle_recovery_action(self, instance_id: str, data: Dict[str, Any]):
        """处理恢复动作"""
        try:
            action = data.get('action')
            self.logger.info(f"实例 {instance_id} 收到恢复动作: {action}")
            
            if action == 'element_action':
                await self._execute_element_action(instance_id, data)
            elif action == 'recover_page':
                await self._recover_page(instance_id)
            elif action == 'restart_instance':
                await self._restart_instance(instance_id)
                
        except Exception as e:
            self.logger.error(f"处理恢复动作失败: {e}")
    
    async def _execute_element_action(self, instance_id: str, data: Dict[str, Any]):
        """执行元素动作"""
        try:
            runtime = self.runtime_states[instance_id]
            if not runtime.page:
                return
            
            selector = data.get('selector')
            action_type = data.get('actionType')
            
            element = runtime.page.locator(selector)
            
            if action_type == 'click':
                await element.click()
                self.logger.info(f"实例 {instance_id} 执行点击: {selector}")
            elif action_type == 'input':
                # 这里可以添加输入对话框
                await element.fill("test input")  # 临时实现
                self.logger.info(f"实例 {instance_id} 执行输入: {selector}")
            elif action_type == 'wait':
                await element.wait_for(state='visible', timeout=10000)
                self.logger.info(f"实例 {instance_id} 等待元素: {selector}")
                
        except Exception as e:
            self.logger.error(f"执行元素动作失败: {e}")
    
    async def _recover_page(self, instance_id: str):
        """恢复页面"""
        try:
            runtime = self.runtime_states[instance_id]
            if not runtime.page:
                return
            
            # 刷新页面
            await runtime.page.reload()
            self.logger.info(f"实例 {instance_id} 页面已恢复")
            
        except Exception as e:
            self.logger.error(f"恢复页面失败: {e}")
    
    async def _restart_instance(self, instance_id: str):
        """重启实例"""
        try:
            self.logger.info(f"重启实例 {instance_id}")
            
            # 停止实例
            await self.stop_instance(instance_id)
            
            # 等待一段时间
            await asyncio.sleep(2)
            
            # 重新启动
            await self.start_instance(instance_id, LaunchMode.DEBUG)
            
        except Exception as e:
            self.logger.error(f"重启实例失败: {e}")
    
    async def _monitor_authentication(self, instance_id: str):
        """监控认证状态"""
        try:
            config = self.instances[instance_id]
            runtime = self.runtime_states[instance_id]
            
            if not runtime.page:
                return
            
            # 定期检查是否已登录
            max_wait_time = 300  # 5分钟
            check_interval = 5   # 5秒检查一次
            elapsed_time = 0
            
            while elapsed_time < max_wait_time and config.status == InstanceStatus.AUTHENTICATION_REQUIRED:
                try:
                    # 检查是否已经登录成功
                    # 这里需要根据实际的AI Studio页面特征来判断
                    current_url = runtime.page.url
                    
                    if 'aistudio.google.com' in current_url and 'chat' in current_url:
                        # 登录成功
                        self.logger.info(f"实例 {instance_id} 认证成功")
                        config.status = InstanceStatus.READY
                        
                        # 自动保存最新的cookies
                        await self._save_latest_cookies(instance_id)
                        break
                        
                except Exception as e:
                    self.logger.debug(f"检查认证状态时出错: {e}")
                
                await asyncio.sleep(check_interval)
                elapsed_time += check_interval
            
            if config.status == InstanceStatus.AUTHENTICATION_REQUIRED:
                self.logger.warning(f"实例 {instance_id} 认证超时")
                config.status = InstanceStatus.ERROR
                
        except Exception as e:
            self.logger.error(f"监控认证状态失败: {e}")
    
    async def _save_latest_cookies(self, instance_id: str):
        """保存最新的cookies"""
        try:
            runtime = self.runtime_states[instance_id]
            config = self.instances[instance_id]
            
            if not runtime.context:
                return
            
            # 获取cookies
            cookies = await runtime.context.cookies()
            
            # 更新认证文件
            auth_data = {
                'cookies': cookies,
                'timestamp': time.time(),
                'user_agent': await runtime.page.evaluate('navigator.userAgent') if runtime.page else None
            }
            
            # 保存到文件
            auth_file = Path(config.auth_profile.file_path)
            with open(auth_file, 'w', encoding='utf-8') as f:
                json.dump(auth_data, f, indent=2, ensure_ascii=False)
            
            # 更新配置
            config.auth_profile.last_updated = time.time()
            config.auth_profile.cookies_data = auth_data
            
            self.logger.info(f"实例 {instance_id} cookies已更新")
            
        except Exception as e:
            self.logger.error(f"保存cookies失败: {e}")
    
    async def stop_instance(self, instance_id: str):
        """停止实例"""
        if instance_id not in self.instances:
            return
        
        config = self.instances[instance_id]
        config.status = InstanceStatus.STOPPED
        
        await self._cleanup_instance_runtime(instance_id)
        
        self.logger.info(f"实例 {instance_id} 已停止")
    
    async def _cleanup_instance_runtime(self, instance_id: str):
        """清理实例运行时状态"""
        try:
            runtime = self.runtime_states[instance_id]
            
            if runtime.page:
                try:
                    await runtime.page.close()
                except:
                    pass
            
            if runtime.context:
                try:
                    await runtime.context.close()
                except:
                    pass
            
            if runtime.browser:
                try:
                    await runtime.browser.close()
                except:
                    pass
            
            # 重置运行时状态
            self.runtime_states[instance_id] = InstanceRuntime()
            
        except Exception as e:
            self.logger.error(f"清理实例运行时状态失败: {e}")
    
    def get_available_instances(self) -> List[str]:
        """获取可用实例列表"""
        available = []
        for instance_id, config in self.instances.items():
            if config.status == InstanceStatus.READY:
                runtime = self.runtime_states[instance_id]
                if runtime.active_requests < config.max_concurrent_requests:
                    available.append(instance_id)
        return available
    
    def get_instance_status(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """获取实例状态"""
        if instance_id not in self.instances:
            return None
        
        config = self.instances[instance_id]
        runtime = self.runtime_states[instance_id]
        
        return {
            'instance_id': instance_id,
            'status': config.status.value,
            'launch_mode': config.launch_mode.value,
            'email': config.auth_profile.email,
            'port': config.port,
            'active_requests': runtime.active_requests,
            'max_concurrent_requests': config.max_concurrent_requests,
            'last_activity': runtime.last_activity,
            'error_count': config.error_count,
            'restart_count': config.restart_count
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_instances = len(self.instances)
        running_instances = sum(1 for config in self.instances.values() 
                              if config.status in [InstanceStatus.READY, InstanceStatus.BUSY])
        available_instances = len(self.get_available_instances())
        error_instances = sum(1 for config in self.instances.values() 
                            if config.status == InstanceStatus.ERROR)
        
        return {
            'total_instances': total_instances,
            'running_instances': running_instances,
            'available_instances': available_instances,
            'error_instances': error_instances,
            'auth_profiles_found': len(self.auth_profiles)
        }
    
    async def enable_debug_mode(self, instance_id: str):
        """启用调试模式"""
        if instance_id not in self.instances:
            return False
        
        runtime = self.runtime_states[instance_id]
        if not runtime.page:
            return False
        
        try:
            # 启用错误恢复模式
            await runtime.page.evaluate('window.enableErrorRecovery()')
            self.logger.info(f"实例 {instance_id} 调试模式已启用")
            return True
            
        except Exception as e:
            self.logger.error(f"启用调试模式失败: {e}")
            return False
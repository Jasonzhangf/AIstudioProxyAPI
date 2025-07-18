"""
PageController模块
封装了所有与Playwright页面直接交互的复杂逻辑。
"""
import asyncio
import random
import string
from typing import Callable, List, Dict, Any, Optional

from playwright.async_api import Page as AsyncPage, expect as expect_async, TimeoutError

from config import (
    TEMPERATURE_INPUT_SELECTOR, MAX_OUTPUT_TOKENS_SELECTOR, STOP_SEQUENCE_INPUT_SELECTOR,
    MAT_CHIP_REMOVE_BUTTON_SELECTOR, TOP_P_INPUT_SELECTOR, SUBMIT_BUTTON_SELECTOR,
    CLEAR_CHAT_BUTTON_SELECTOR, CLEAR_CHAT_CONFIRM_BUTTON_SELECTOR, OVERLAY_SELECTOR,
    PROMPT_TEXTAREA_SELECTOR, PROMPT_TEXTAREA_SELECTOR_ALT, PROMPT_TEXTAREA_SELECTOR_ALT2, RESPONSE_CONTAINER_SELECTOR, RESPONSE_TEXT_SELECTOR,
    EDIT_MESSAGE_BUTTON_SELECTOR,USE_URL_CONTEXT_SELECTOR,UPLOAD_BUTTON_SELECTOR,
    SET_THINKING_BUDGET_TOGGLE_SELECTOR, THINKING_BUDGET_INPUT_SELECTOR,
    GROUNDING_WITH_GOOGLE_SEARCH_TOGGLE_SELECTOR
)
from config import (
    CLICK_TIMEOUT_MS, WAIT_FOR_ELEMENT_TIMEOUT_MS, CLEAR_CHAT_VERIFY_TIMEOUT_MS,
    DEFAULT_TEMPERATURE, DEFAULT_MAX_OUTPUT_TOKENS, DEFAULT_STOP_SEQUENCES, DEFAULT_TOP_P,
    ENABLE_URL_CONTEXT, ENABLE_THINKING_BUDGET, DEFAULT_THINKING_BUDGET, ENABLE_GOOGLE_SEARCH
)
from models import ClientDisconnectedError
from .operations import save_error_snapshot, _wait_for_response_completion, _get_final_response_content

class PageController:
    """封装了与AI Studio页面交互的所有操作。"""

    def __init__(self, page: AsyncPage, logger, req_id: str, is_streaming: bool = True):
        self.page = page
        self.logger = logger
        self.req_id = req_id
        self.is_streaming = is_streaming

    async def _check_disconnect(self, check_client_disconnected: Callable, stage: str):
        """检查客户端是否断开连接。"""
        if check_client_disconnected(stage):
            raise ClientDisconnectedError(f"[{self.req_id}] Client disconnected at stage: {stage}")

    async def _get_prompt_textarea_locator(self):
        """智能获取提示输入框的定位器，尝试多个选择器"""
        selectors = [
            (PROMPT_TEXTAREA_SELECTOR, "主选择器"),
            (PROMPT_TEXTAREA_SELECTOR_ALT, "备用选择器1"),
            (PROMPT_TEXTAREA_SELECTOR_ALT2, "备用选择器2")
        ]
        
        for selector, desc in selectors:
            try:
                locator = self.page.locator(selector)
                await expect_async(locator).to_be_visible(timeout=2000)
                self.logger.info(f"[{self.req_id}] 使用{desc}: {selector}")
                return locator
            except Exception as e:
                self.logger.debug(f"[{self.req_id}] {desc} 不可用: {e}")
                continue
        
        # 如果所有选择器都失败，返回主选择器让上层处理错误
        self.logger.error(f"[{self.req_id}] 所有提示输入框选择器都不可用")
        return self.page.locator(PROMPT_TEXTAREA_SELECTOR)

    async def _humanized_input(self, locator, text: str, check_client_disconnected: Callable):
        """真实人性化输入：输入随机字符→删除→高效填充→再输入随机字符→删除→发送"""
        try:
            # 确保输入框获得焦点
            await locator.focus(timeout=3000)
            await self._check_disconnect(check_client_disconnected, "人性化输入 - 获得焦点后")
            await asyncio.sleep(0.05)
            
            # 第一阶段：按字输入随机字符
            first_chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(3, 5)))
            self.logger.info(f"[{self.req_id}] 第一阶段：按字输入随机字符 '{first_chars}'")
            for char in first_chars:
                await self.page.keyboard.type(char)
                await asyncio.sleep(random.uniform(0.08, 0.25))  # 模拟真实打字速度
            
            await self._check_disconnect(check_client_disconnected, "人性化输入 - 第一阶段输入后")
            
            # 短暂停顿（模拟犹豫）
            await asyncio.sleep(random.uniform(0.2, 0.5))
            
            # 删除第一阶段字符
            self.logger.info(f"[{self.req_id}] 删除第一阶段字符...")
            for _ in range(len(first_chars)):
                await self.page.keyboard.press('Backspace')
                await asyncio.sleep(random.uniform(0.05, 0.15))
            
            await self._check_disconnect(check_client_disconnected, "人性化输入 - 第一阶段删除后")
            
            # 思考停顿
            think_time = random.uniform(0.4, 0.9)
            self.logger.info(f"[{self.req_id}] 思考停顿 {think_time:.2f} 秒...")
            await asyncio.sleep(think_time)
            
            # 第二阶段：高效填充真实内容
            self.logger.info(f"[{self.req_id}] 第二阶段：高效填充真实内容 ({len(text)} 字符)")
            await locator.fill(text, timeout=5000)
            await self._check_disconnect(check_client_disconnected, "人性化输入 - 真实内容填充后")
            
            # 短暂停顿（模拟检查内容）
            await asyncio.sleep(random.uniform(0.3, 0.7))
            
            # 第三阶段：再次按字输入一些字符（模拟想添加更多内容）
            additional_chars = ''.join(random.choices(string.ascii_lowercase + ' ', k=random.randint(2, 4)))
            self.logger.info(f"[{self.req_id}] 第三阶段：输入额外字符 '{additional_chars}'")
            for char in additional_chars:
                await self.page.keyboard.type(char)
                await asyncio.sleep(random.uniform(0.1, 0.3))
            
            await self._check_disconnect(check_client_disconnected, "人性化输入 - 第三阶段输入后")
            
            # 再次停顿（模拟重新考虑）
            await asyncio.sleep(random.uniform(0.2, 0.5))
            
            # 删除第三阶段字符
            self.logger.info(f"[{self.req_id}] 删除第三阶段字符...")
            for _ in range(len(additional_chars)):
                await self.page.keyboard.press('Backspace')
                await asyncio.sleep(random.uniform(0.03, 0.1))
            
            await self._check_disconnect(check_client_disconnected, "人性化输入 - 第三阶段删除后")
            
            # 触发必要的事件
            await locator.evaluate(
                '''
                (element) => {
                    element.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
                    element.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
                }
                '''
            )
            
            self.logger.info(f"[{self.req_id}] ✅ 真实人性化输入完成 (3阶段操作)")
            
        except Exception as e:
            self.logger.error(f"[{self.req_id}] ❌ 人性化输入失败: {e}")
            # 如果人性化输入失败，回退到直接填充
            await locator.fill(text, timeout=5000)
            await locator.evaluate(
                '''
                (element, text) => {
                    element.value = text;
                    element.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
                    element.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
                }
                ''',
                text
            )

    async def adjust_parameters(self, request_params: Dict[str, Any], page_params_cache: Dict[str, Any], params_cache_lock: asyncio.Lock, model_id_to_use: str, parsed_model_list: List[Dict[str, Any]], check_client_disconnected: Callable):
        """调整所有请求参数。"""
        self.logger.info(f"[{self.req_id}] 开始调整所有请求参数...")
        await self._check_disconnect(check_client_disconnected, "Start Parameter Adjustment")

        # 调整温度
        temp_to_set = request_params.get('temperature', DEFAULT_TEMPERATURE)
        await self._adjust_temperature(temp_to_set, page_params_cache, params_cache_lock, check_client_disconnected)
        await self._check_disconnect(check_client_disconnected, "After Temperature Adjustment")

        # 调整最大Token
        max_tokens_to_set = request_params.get('max_output_tokens', DEFAULT_MAX_OUTPUT_TOKENS)
        await self._adjust_max_tokens(max_tokens_to_set, page_params_cache, params_cache_lock, model_id_to_use, parsed_model_list, check_client_disconnected)
        await self._check_disconnect(check_client_disconnected, "After Max Tokens Adjustment")

        # 调整停止序列
        stop_to_set = request_params.get('stop', DEFAULT_STOP_SEQUENCES)
        await self._adjust_stop_sequences(stop_to_set, page_params_cache, params_cache_lock, check_client_disconnected)
        await self._check_disconnect(check_client_disconnected, "After Stop Sequences Adjustment")

        # 调整Top P
        top_p_to_set = request_params.get('top_p', DEFAULT_TOP_P)
        await self._adjust_top_p(top_p_to_set, check_client_disconnected)
        await self._check_disconnect(check_client_disconnected, "End Parameter Adjustment")

        # 确保工具面板已展开，以便调整高级设置
        await self._ensure_tools_panel_expanded(check_client_disconnected)

        # 调整URL CONTEXT
        if ENABLE_URL_CONTEXT:
            await self._open_url_content(check_client_disconnected)
        else:
            self.logger.info(f"[{self.req_id}] URL Context 功能已禁用，跳过调整。")

        # 调整“思考预算”
        await self._handle_thinking_budget(request_params, check_client_disconnected)

        # 调整 Google Search 开关
        await self._adjust_google_search(request_params, check_client_disconnected)

    async def _handle_thinking_budget(self, request_params: Dict[str, Any], check_client_disconnected: Callable):
        """处理思考预算的调整逻辑。"""
        reasoning_effort = request_params.get('reasoning_effort')

        # 检查用户是否明确禁用了思考预算
        should_disable_budget = isinstance(reasoning_effort, str) and reasoning_effort.lower() == 'none'

        if should_disable_budget:
            self.logger.info(f"[{self.req_id}] 用户通过 reasoning_effort='none' 明确禁用思考预算。")
            await self._control_thinking_budget_toggle(should_be_checked=False, check_client_disconnected=check_client_disconnected)
        elif reasoning_effort is not None:
            # 用户指定了非 'none' 的值，则开启并设置
            self.logger.info(f"[{self.req_id}] 用户指定了 reasoning_effort: {reasoning_effort}，将启用并设置思考预算。")
            await self._control_thinking_budget_toggle(should_be_checked=True, check_client_disconnected=check_client_disconnected)
            await self._adjust_thinking_budget(reasoning_effort, check_client_disconnected)
        else:
            # 用户未指定，根据默认配置
            self.logger.info(f"[{self.req_id}] 用户未指定 reasoning_effort，根据默认配置 ENABLE_THINKING_BUDGET: {ENABLE_THINKING_BUDGET}。")
            await self._control_thinking_budget_toggle(should_be_checked=ENABLE_THINKING_BUDGET, check_client_disconnected=check_client_disconnected)
            if ENABLE_THINKING_BUDGET:
                # 如果默认开启，则使用默认值
                await self._adjust_thinking_budget(None, check_client_disconnected)

    def _parse_thinking_budget(self, reasoning_effort: Optional[Any]) -> Optional[int]:
        """从 reasoning_effort 解析出 token_budget。"""
        token_budget = None
        if reasoning_effort is None:
            token_budget = DEFAULT_THINKING_BUDGET
            self.logger.info(f"[{self.req_id}] 'reasoning_effort' 为空，使用默认思考预算: {token_budget}")
        elif isinstance(reasoning_effort, int):
            token_budget = reasoning_effort
        elif isinstance(reasoning_effort, str):
            if reasoning_effort.lower() == 'none':
                token_budget = DEFAULT_THINKING_BUDGET
                self.logger.info(f"[{self.req_id}] 'reasoning_effort' 为 'none' 字符串，使用默认思考预算: {token_budget}")
            else:
                effort_map = {
                    "low": 1000,
                    "medium": 8000,
                    "high": 24000
                }
                token_budget = effort_map.get(reasoning_effort.lower())
                if token_budget is None:
                    try:
                        token_budget = int(reasoning_effort)
                    except (ValueError, TypeError):
                        pass # token_budget remains None
        
        if token_budget is None:
             self.logger.warning(f"[{self.req_id}] 无法从 '{reasoning_effort}' (类型: {type(reasoning_effort)}) 解析出有效的 token_budget。")

        return token_budget

    async def _adjust_thinking_budget(self, reasoning_effort: Optional[Any], check_client_disconnected: Callable):
        """根据 reasoning_effort 调整思考预算。"""
        self.logger.info(f"[{self.req_id}] 检查并调整思考预算，输入值: {reasoning_effort}")
        
        token_budget = self._parse_thinking_budget(reasoning_effort)

        if token_budget is None:
            self.logger.warning(f"[{self.req_id}] 无效的 reasoning_effort 值: '{reasoning_effort}'。跳过调整。")
            return

        budget_input_locator = self.page.locator(THINKING_BUDGET_INPUT_SELECTOR)
        
        try:
            await expect_async(budget_input_locator).to_be_visible(timeout=5000)
            await self._check_disconnect(check_client_disconnected, "思考预算调整 - 输入框可见后")
            
            self.logger.info(f"[{self.req_id}] 设置思考预算为: {token_budget}")
            await budget_input_locator.fill(str(token_budget), timeout=5000)
            await self._check_disconnect(check_client_disconnected, "思考预算调整 - 填充输入框后")

            # 验证
            await asyncio.sleep(0.1)
            new_value_str = await budget_input_locator.input_value(timeout=3000)
            if int(new_value_str) == token_budget:
                self.logger.info(f"[{self.req_id}] ✅ 思考预算已成功更新为: {new_value_str}")
            else:
                self.logger.warning(f"[{self.req_id}] ⚠️ 思考预算更新后验证失败。页面显示: {new_value_str}, 期望: {token_budget}")

        except Exception as e:
            self.logger.error(f"[{self.req_id}] ❌ 调整思考预算时出错: {e}")
            if isinstance(e, ClientDisconnectedError):
                raise

    def _should_enable_google_search(self, request_params: Dict[str, Any]) -> bool:
        """根据请求参数或默认配置决定是否应启用 Google Search。"""
        if 'tools' in request_params and request_params.get('tools') is not None:
            tools = request_params.get('tools')
            has_google_search_tool = False
            if isinstance(tools, list):
                for tool in tools:
                    if isinstance(tool, dict):
                        if tool.get('google_search_retrieval') is not None:
                            has_google_search_tool = True
                            break
                        if tool.get('function', {}).get('name') == 'googleSearch':
                            has_google_search_tool = True
                            break
            self.logger.info(f"[{self.req_id}] 请求中包含 'tools' 参数。检测到 Google Search 工具: {has_google_search_tool}。")
            return has_google_search_tool
        else:
            self.logger.info(f"[{self.req_id}] 请求中不包含 'tools' 参数。使用默认配置 ENABLE_GOOGLE_SEARCH: {ENABLE_GOOGLE_SEARCH}。")
            return ENABLE_GOOGLE_SEARCH

    async def _adjust_google_search(self, request_params: Dict[str, Any], check_client_disconnected: Callable):
        """根据请求参数或默认配置，双向控制 Google Search 开关。"""
        self.logger.info(f"[{self.req_id}] 检查并调整 Google Search 开关...")

        should_enable_search = self._should_enable_google_search(request_params)

        toggle_selector = GROUNDING_WITH_GOOGLE_SEARCH_TOGGLE_SELECTOR
        
        try:
            toggle_locator = self.page.locator(toggle_selector)
            await expect_async(toggle_locator).to_be_visible(timeout=5000)
            await self._check_disconnect(check_client_disconnected, "Google Search 开关 - 元素可见后")

            is_checked_str = await toggle_locator.get_attribute("aria-checked")
            is_currently_checked = is_checked_str == "true"
            self.logger.info(f"[{self.req_id}] Google Search 开关当前状态: '{is_checked_str}'。期望状态: {should_enable_search}")

            if should_enable_search != is_currently_checked:
                action = "打开" if should_enable_search else "关闭"
                self.logger.info(f"[{self.req_id}] Google Search 开关状态与期望不符。正在点击以{action}...")
                await toggle_locator.click(timeout=CLICK_TIMEOUT_MS)
                await self._check_disconnect(check_client_disconnected, f"Google Search 开关 - 点击{action}后")
                await asyncio.sleep(0.5) # 等待UI更新
                new_state = await toggle_locator.get_attribute("aria-checked")
                if (new_state == "true") == should_enable_search:
                    self.logger.info(f"[{self.req_id}] ✅ Google Search 开关已成功{action}。")
                else:
                    self.logger.warning(f"[{self.req_id}] ⚠️ Google Search 开关{action}失败。当前状态: '{new_state}'")
            else:
                self.logger.info(f"[{self.req_id}] Google Search 开关已处于期望状态，无需操作。")

        except Exception as e:
            self.logger.error(f"[{self.req_id}] ❌ 操作 'Google Search toggle' 开关时发生错误: {e}")
            if isinstance(e, ClientDisconnectedError):
                 raise

    async def _ensure_tools_panel_expanded(self, check_client_disconnected: Callable):
        """确保包含高级工具（URL上下文、思考预算等）的面板是展开的。"""
        self.logger.info(f"[{self.req_id}] 检查并确保工具面板已展开...")
        try:
            collapse_tools_locator = self.page.locator('button[aria-label="Expand or collapse tools"]')
            await expect_async(collapse_tools_locator).to_be_visible(timeout=5000)
            
            grandparent_locator = collapse_tools_locator.locator("xpath=../..")
            class_string = await grandparent_locator.get_attribute("class", timeout=3000)

            if class_string and "expanded" not in class_string.split():
                self.logger.info(f"[{self.req_id}] 工具面板未展开，正在点击以展开...")
                await collapse_tools_locator.click(timeout=CLICK_TIMEOUT_MS)
                await self._check_disconnect(check_client_disconnected, "展开工具面板后")
                # 等待展开动画完成
                await expect_async(grandparent_locator).to_have_class(re.compile(r'.*expanded.*'), timeout=5000)
                self.logger.info(f"[{self.req_id}] ✅ 工具面板已成功展开。")
            else:
                self.logger.info(f"[{self.req_id}] 工具面板已处于展开状态。")
        except Exception as e:
            self.logger.error(f"[{self.req_id}] ❌ 展开工具面板时发生错误: {e}")
            # 即使出错，也继续尝试执行后续操作，但记录错误
            if isinstance(e, ClientDisconnectedError):
                raise

    async def _open_url_content(self,check_client_disconnected: Callable):
        """仅负责打开 URL Context 开关，前提是面板已展开。"""
        try:
            self.logger.info(f"[{self.req_id}] 检查并启用 URL Context 开关...")
            use_url_content_selector = self.page.locator(USE_URL_CONTEXT_SELECTOR)
            await expect_async(use_url_content_selector).to_be_visible(timeout=5000)
            
            is_checked = await use_url_content_selector.get_attribute("aria-checked")
            if "false" == is_checked:
                self.logger.info(f"[{self.req_id}] URL Context 开关未开启，正在点击以开启...")
                await use_url_content_selector.click(timeout=CLICK_TIMEOUT_MS)
                await self._check_disconnect(check_client_disconnected, "点击URLCONTEXT后")
                self.logger.info(f"[{self.req_id}] ✅ URL Context 开关已点击。")
            else:
                self.logger.info(f"[{self.req_id}] URL Context 开关已处于开启状态。")
        except Exception as e:
            self.logger.error(f"[{self.req_id}] ❌ 操作 USE_URL_CONTEXT_SELECTOR 时发生错误:{e}。")
            if isinstance(e, ClientDisconnectedError):
                raise

    async def _control_thinking_budget_toggle(self, should_be_checked: bool, check_client_disconnected: Callable):
        """
        根据 should_be_checked 的值，控制 "Thinking Budget" 滑块开关的状态。
        """
        toggle_selector = SET_THINKING_BUDGET_TOGGLE_SELECTOR
        self.logger.info(f"[{self.req_id}] 控制 'Thinking Budget' 开关，期望状态: {'选中' if should_be_checked else '未选中'}...")

        try:
            toggle_locator = self.page.locator(toggle_selector)
            await expect_async(toggle_locator).to_be_visible(timeout=5000)
            await self._check_disconnect(check_client_disconnected, "思考预算开关 - 元素可见后")

            is_checked_str = await toggle_locator.get_attribute("aria-checked")
            current_state_is_checked = is_checked_str == "true"
            self.logger.info(f"[{self.req_id}] 思考预算开关当前 'aria-checked' 状态: {is_checked_str} (当前是否选中: {current_state_is_checked})")

            if current_state_is_checked != should_be_checked:
                action = "启用" if should_be_checked else "禁用"
                self.logger.info(f"[{self.req_id}] 思考预算开关当前状态与期望不符，正在点击以{action}...")
                await toggle_locator.click(timeout=CLICK_TIMEOUT_MS)
                await self._check_disconnect(check_client_disconnected, f"思考预算开关 - 点击{action}后")

                await asyncio.sleep(0.5)
                new_state_str = await toggle_locator.get_attribute("aria-checked")
                new_state_is_checked = new_state_str == "true"

                if new_state_is_checked == should_be_checked:
                    self.logger.info(f"[{self.req_id}] ✅ 'Thinking Budget' 开关已成功{action}。新状态: {new_state_str}")
                else:
                    self.logger.warning(f"[{self.req_id}] ⚠️ 'Thinking Budget' 开关{action}后验证失败。期望状态: '{should_be_checked}', 实际状态: '{new_state_str}'")
            else:
                self.logger.info(f"[{self.req_id}] 'Thinking Budget' 开关已处于期望状态，无需操作。")

        except Exception as e:
            self.logger.error(f"[{self.req_id}] ❌ 操作 'Thinking Budget toggle' 开关时发生错误: {e}")
            if isinstance(e, ClientDisconnectedError):
                raise
    async def _adjust_temperature(self, temperature: float, page_params_cache: dict, params_cache_lock: asyncio.Lock, check_client_disconnected: Callable):
        """调整温度参数。"""
        async with params_cache_lock:
            self.logger.info(f"[{self.req_id}] 检查并调整温度设置...")
            clamped_temp = max(0.0, min(2.0, temperature))
            if clamped_temp != temperature:
                self.logger.warning(f"[{self.req_id}] 请求的温度 {temperature} 超出范围 [0, 2]，已调整为 {clamped_temp}")

            cached_temp = page_params_cache.get("temperature")
            if cached_temp is not None and abs(cached_temp - clamped_temp) < 0.001:
                self.logger.info(f"[{self.req_id}] 温度 ({clamped_temp}) 与缓存值 ({cached_temp}) 一致。跳过页面交互。")
                return

            self.logger.info(f"[{self.req_id}] 请求温度 ({clamped_temp}) 与缓存值 ({cached_temp}) 不一致或缓存中无值。需要与页面交互。")
            temp_input_locator = self.page.locator(TEMPERATURE_INPUT_SELECTOR)


            try:
                await expect_async(temp_input_locator).to_be_visible(timeout=5000)
                await self._check_disconnect(check_client_disconnected, "温度调整 - 输入框可见后")

                current_temp_str = await temp_input_locator.input_value(timeout=3000)
                await self._check_disconnect(check_client_disconnected, "温度调整 - 读取输入框值后")

                current_temp_float = float(current_temp_str)
                self.logger.info(f"[{self.req_id}] 页面当前温度: {current_temp_float}, 请求调整后温度: {clamped_temp}")

                if abs(current_temp_float - clamped_temp) < 0.001:
                    self.logger.info(f"[{self.req_id}] 页面当前温度 ({current_temp_float}) 与请求温度 ({clamped_temp}) 一致。更新缓存并跳过写入。")
                    page_params_cache["temperature"] = current_temp_float
                else:
                    self.logger.info(f"[{self.req_id}] 页面温度 ({current_temp_float}) 与请求温度 ({clamped_temp}) 不同，正在更新...")
                    await temp_input_locator.fill(str(clamped_temp), timeout=5000)
                    await self._check_disconnect(check_client_disconnected, "温度调整 - 填充输入框后")

                    await asyncio.sleep(0.1)
                    new_temp_str = await temp_input_locator.input_value(timeout=3000)
                    new_temp_float = float(new_temp_str)

                    if abs(new_temp_float - clamped_temp) < 0.001:
                        self.logger.info(f"[{self.req_id}] ✅ 温度已成功更新为: {new_temp_float}。更新缓存。")
                        page_params_cache["temperature"] = new_temp_float
                    else:
                        self.logger.warning(f"[{self.req_id}] ⚠️ 温度更新后验证失败。页面显示: {new_temp_float}, 期望: {clamped_temp}。清除缓存中的温度。")
                        page_params_cache.pop("temperature", None)
                        await save_error_snapshot(f"temperature_verify_fail_{self.req_id}")

            except ValueError as ve:
                self.logger.error(f"[{self.req_id}] 转换温度值为浮点数时出错. 错误: {ve}。清除缓存中的温度。")
                page_params_cache.pop("temperature", None)
                await save_error_snapshot(f"temperature_value_error_{self.req_id}")
            except Exception as pw_err:
                self.logger.error(f"[{self.req_id}] ❌ 操作温度输入框时发生错误: {pw_err}。清除缓存中的温度。")
                page_params_cache.pop("temperature", None)
                await save_error_snapshot(f"temperature_playwright_error_{self.req_id}")
                if isinstance(pw_err, ClientDisconnectedError):
                    raise

    async def _adjust_max_tokens(self, max_tokens: int, page_params_cache: dict, params_cache_lock: asyncio.Lock, model_id_to_use: str, parsed_model_list: list, check_client_disconnected: Callable):
        """调整最大输出Token参数。"""
        async with params_cache_lock:
            self.logger.info(f"[{self.req_id}] 检查并调整最大输出 Token 设置...")
            min_val_for_tokens = 1
            max_val_for_tokens_from_model = 65536

            if model_id_to_use and parsed_model_list:
                current_model_data = next((m for m in parsed_model_list if m.get("id") == model_id_to_use), None)
                if current_model_data and current_model_data.get("supported_max_output_tokens") is not None:
                    try:
                        supported_tokens = int(current_model_data["supported_max_output_tokens"])
                        if supported_tokens > 0:
                            max_val_for_tokens_from_model = supported_tokens
                        else:
                            self.logger.warning(f"[{self.req_id}] 模型 {model_id_to_use} supported_max_output_tokens 无效: {supported_tokens}")
                    except (ValueError, TypeError):
                        self.logger.warning(f"[{self.req_id}] 模型 {model_id_to_use} supported_max_output_tokens 解析失败")

            clamped_max_tokens = max(min_val_for_tokens, min(max_val_for_tokens_from_model, max_tokens))
            if clamped_max_tokens != max_tokens:
                self.logger.warning(f"[{self.req_id}] 请求的最大输出 Tokens {max_tokens} 超出模型范围，已调整为 {clamped_max_tokens}")

            cached_max_tokens = page_params_cache.get("max_output_tokens")
            if cached_max_tokens is not None and cached_max_tokens == clamped_max_tokens:
                self.logger.info(f"[{self.req_id}] 最大输出 Tokens ({clamped_max_tokens}) 与缓存值一致。跳过页面交互。")
                return

            max_tokens_input_locator = self.page.locator(MAX_OUTPUT_TOKENS_SELECTOR)

            try:
                await expect_async(max_tokens_input_locator).to_be_visible(timeout=5000)
                await self._check_disconnect(check_client_disconnected, "最大输出Token调整 - 输入框可见后")

                current_max_tokens_str = await max_tokens_input_locator.input_value(timeout=3000)
                current_max_tokens_int = int(current_max_tokens_str)

                if current_max_tokens_int == clamped_max_tokens:
                    self.logger.info(f"[{self.req_id}] 页面当前最大输出 Tokens ({current_max_tokens_int}) 与请求值 ({clamped_max_tokens}) 一致。更新缓存并跳过写入。")
                    page_params_cache["max_output_tokens"] = current_max_tokens_int
                else:
                    self.logger.info(f"[{self.req_id}] 页面最大输出 Tokens ({current_max_tokens_int}) 与请求值 ({clamped_max_tokens}) 不同，正在更新...")
                    await max_tokens_input_locator.fill(str(clamped_max_tokens), timeout=5000)
                    await self._check_disconnect(check_client_disconnected, "最大输出Token调整 - 填充输入框后")

                    await asyncio.sleep(0.1)
                    new_max_tokens_str = await max_tokens_input_locator.input_value(timeout=3000)
                    new_max_tokens_int = int(new_max_tokens_str)

                    if new_max_tokens_int == clamped_max_tokens:
                        self.logger.info(f"[{self.req_id}] ✅ 最大输出 Tokens 已成功更新为: {new_max_tokens_int}")
                        page_params_cache["max_output_tokens"] = new_max_tokens_int
                    else:
                        self.logger.warning(f"[{self.req_id}] ⚠️ 最大输出 Tokens 更新后验证失败。页面显示: {new_max_tokens_int}, 期望: {clamped_max_tokens}。清除缓存。")
                        page_params_cache.pop("max_output_tokens", None)
                        await save_error_snapshot(f"max_tokens_verify_fail_{self.req_id}")

            except (ValueError, TypeError) as ve:
                self.logger.error(f"[{self.req_id}] 转换最大输出 Tokens 值时出错: {ve}。清除缓存。")
                page_params_cache.pop("max_output_tokens", None)
                await save_error_snapshot(f"max_tokens_value_error_{self.req_id}")
            except Exception as e:
                self.logger.error(f"[{self.req_id}] ❌ 调整最大输出 Tokens 时出错: {e}。清除缓存。")
                page_params_cache.pop("max_output_tokens", None)
                await save_error_snapshot(f"max_tokens_error_{self.req_id}")
                if isinstance(e, ClientDisconnectedError):
                    raise
    
    async def _adjust_stop_sequences(self, stop_sequences, page_params_cache: dict, params_cache_lock: asyncio.Lock, check_client_disconnected: Callable):
        """调整停止序列参数。"""
        async with params_cache_lock:
            self.logger.info(f"[{self.req_id}] 检查并设置停止序列...")

            # 处理不同类型的stop_sequences输入
            normalized_requested_stops = set()
            if stop_sequences is not None:
                if isinstance(stop_sequences, str):
                    # 单个字符串
                    if stop_sequences.strip():
                        normalized_requested_stops.add(stop_sequences.strip())
                elif isinstance(stop_sequences, list):
                    # 字符串列表
                    for s in stop_sequences:
                        if isinstance(s, str) and s.strip():
                            normalized_requested_stops.add(s.strip())

            cached_stops_set = page_params_cache.get("stop_sequences")

            if cached_stops_set is not None and cached_stops_set == normalized_requested_stops:
                self.logger.info(f"[{self.req_id}] 请求的停止序列与缓存值一致。跳过页面交互。")
                return

            stop_input_locator = self.page.locator(STOP_SEQUENCE_INPUT_SELECTOR)
            remove_chip_buttons_locator = self.page.locator(MAT_CHIP_REMOVE_BUTTON_SELECTOR)

            try:
                # 清空已有的停止序列
                initial_chip_count = await remove_chip_buttons_locator.count()
                removed_count = 0
                max_removals = initial_chip_count + 5

                while await remove_chip_buttons_locator.count() > 0 and removed_count < max_removals:
                    await self._check_disconnect(check_client_disconnected, "停止序列清除 - 循环开始")
                    try:
                        await remove_chip_buttons_locator.first.click(timeout=2000)
                        removed_count += 1
                        await asyncio.sleep(0.15)
                    except Exception:
                        break

                # 添加新的停止序列
                if normalized_requested_stops:
                    await expect_async(stop_input_locator).to_be_visible(timeout=5000)
                    for seq in normalized_requested_stops:
                        await stop_input_locator.fill(seq, timeout=3000)
                        await stop_input_locator.press("Enter", timeout=3000)
                        await asyncio.sleep(0.2)

                page_params_cache["stop_sequences"] = normalized_requested_stops
                self.logger.info(f"[{self.req_id}] ✅ 停止序列已成功设置。缓存已更新。")

            except Exception as e:
                self.logger.error(f"[{self.req_id}] ❌ 设置停止序列时出错: {e}")
                page_params_cache.pop("stop_sequences", None)
                await save_error_snapshot(f"stop_sequence_error_{self.req_id}")
                if isinstance(e, ClientDisconnectedError):
                    raise

    async def _adjust_top_p(self, top_p: float, check_client_disconnected: Callable):
        """调整Top P参数。"""
        self.logger.info(f"[{self.req_id}] 检查并调整 Top P 设置...")
        clamped_top_p = max(0.0, min(1.0, top_p))

        if abs(clamped_top_p - top_p) > 1e-9:
            self.logger.warning(f"[{self.req_id}] 请求的 Top P {top_p} 超出范围 [0, 1]，已调整为 {clamped_top_p}")

        top_p_input_locator = self.page.locator(TOP_P_INPUT_SELECTOR)
        try:
            await expect_async(top_p_input_locator).to_be_visible(timeout=5000)
            await self._check_disconnect(check_client_disconnected, "Top P 调整 - 输入框可见后")

            current_top_p_str = await top_p_input_locator.input_value(timeout=3000)
            current_top_p_float = float(current_top_p_str)

            if abs(current_top_p_float - clamped_top_p) > 1e-9:
                self.logger.info(f"[{self.req_id}] 页面 Top P ({current_top_p_float}) 与请求值 ({clamped_top_p}) 不同，正在更新...")
                await top_p_input_locator.fill(str(clamped_top_p), timeout=5000)
                await self._check_disconnect(check_client_disconnected, "Top P 调整 - 填充输入框后")

                # 验证设置是否成功
                await asyncio.sleep(0.1)
                new_top_p_str = await top_p_input_locator.input_value(timeout=3000)
                new_top_p_float = float(new_top_p_str)

                if abs(new_top_p_float - clamped_top_p) <= 1e-9:
                    self.logger.info(f"[{self.req_id}] ✅ Top P 已成功更新为: {new_top_p_float}")
                else:
                    self.logger.warning(f"[{self.req_id}] ⚠️ Top P 更新后验证失败。页面显示: {new_top_p_float}, 期望: {clamped_top_p}")
                    await save_error_snapshot(f"top_p_verify_fail_{self.req_id}")
            else:
                self.logger.info(f"[{self.req_id}] 页面 Top P ({current_top_p_float}) 与请求值 ({clamped_top_p}) 一致，无需更改")

        except (ValueError, TypeError) as ve:
            self.logger.error(f"[{self.req_id}] 转换 Top P 值时出错: {ve}")
            await save_error_snapshot(f"top_p_value_error_{self.req_id}")
        except Exception as e:
            self.logger.error(f"[{self.req_id}] ❌ 调整 Top P 时出错: {e}")
            await save_error_snapshot(f"top_p_error_{self.req_id}")
            if isinstance(e, ClientDisconnectedError):
                raise

    async def clear_chat_history(self, check_client_disconnected: Callable):
        """清空聊天记录。"""
        self.logger.info(f"[{self.req_id}] 开始清空聊天记录...")
        await self._check_disconnect(check_client_disconnected, "Start Clear Chat")

        try:
            # 一般是使用流式代理时遇到,流式输出已结束,但页面上AI仍回复个不停,此时会锁住清空按钮,但页面仍是/new_chat,而跳过后续清空操作
            # 导致后续请求无法发出而卡住,故先检查并点击发送按钮(此时是停止功能)
            submit_button_locator = self.page.locator(SUBMIT_BUTTON_SELECTOR)
            try:
                self.logger.info(f"[{self.req_id}] 尝试检查发送按钮状态...")
                # 使用较短的超时时间（1秒），避免长时间阻塞，因为这不是清空流程的常见步骤
                await expect_async(submit_button_locator).to_be_enabled(timeout=1000)
                self.logger.info(f"[{self.req_id}] 发送按钮可用，尝试点击并等待1秒...")
                await submit_button_locator.click(timeout=CLICK_TIMEOUT_MS)
                await asyncio.sleep(1.0)
                self.logger.info(f"[{self.req_id}] 发送按钮点击并等待完成。")
            except Exception as e_submit:
                # 如果发送按钮不可用、超时或发生Playwright相关错误，记录日志并继续
                self.logger.info(f"[{self.req_id}] 发送按钮不可用或检查/点击时发生Playwright错误。符合预期,继续检查清空按钮。")

            clear_chat_button_locator = self.page.locator(CLEAR_CHAT_BUTTON_SELECTOR)
            confirm_button_locator = self.page.locator(CLEAR_CHAT_CONFIRM_BUTTON_SELECTOR)
            overlay_locator = self.page.locator(OVERLAY_SELECTOR)

            can_attempt_clear = False
            try:
                await expect_async(clear_chat_button_locator).to_be_enabled(timeout=3000)
                can_attempt_clear = True
                self.logger.info(f"[{self.req_id}] \"清空聊天\"按钮可用，继续清空流程。")
            except Exception as e_enable:
                is_new_chat_url = '/prompts/new_chat' in self.page.url.rstrip('/')
                if is_new_chat_url:
                    self.logger.info(f"[{self.req_id}] \"清空聊天\"按钮不可用 (预期，因为在 new_chat 页面)。跳过清空操作。")
                else:
                    self.logger.warning(f"[{self.req_id}] 等待\"清空聊天\"按钮可用失败: {e_enable}。清空操作可能无法执行。")

            await self._check_disconnect(check_client_disconnected, "清空聊天 - \"清空聊天\"按钮可用性检查后")

            if can_attempt_clear:
                await self._execute_chat_clear(clear_chat_button_locator, confirm_button_locator, overlay_locator, check_client_disconnected)
                await self._verify_chat_cleared(check_client_disconnected)

        except Exception as e_clear:
            self.logger.error(f"[{self.req_id}] 清空聊天过程中发生错误: {e_clear}")
            if not (isinstance(e_clear, ClientDisconnectedError) or (hasattr(e_clear, 'name') and 'Disconnect' in e_clear.name)):
                await save_error_snapshot(f"clear_chat_error_{self.req_id}")
            raise

    async def _execute_chat_clear(self, clear_chat_button_locator, confirm_button_locator, overlay_locator, check_client_disconnected: Callable):
        """执行清空聊天操作"""
        overlay_initially_visible = False
        try:
            if await overlay_locator.is_visible(timeout=1000):
                overlay_initially_visible = True
                self.logger.info(f"[{self.req_id}] 清空聊天确认遮罩层已可见。直接点击\"继续\"。")
        except TimeoutError:
            self.logger.info(f"[{self.req_id}] 清空聊天确认遮罩层初始不可见 (检查超时或未找到)。")
            overlay_initially_visible = False
        except Exception as e_vis_check:
            self.logger.warning(f"[{self.req_id}] 检查遮罩层可见性时发生错误: {e_vis_check}。假定不可见。")
            overlay_initially_visible = False

        await self._check_disconnect(check_client_disconnected, "清空聊天 - 初始遮罩层检查后")

        if overlay_initially_visible:
            self.logger.info(f"[{self.req_id}] 点击\"继续\"按钮 (遮罩层已存在): {CLEAR_CHAT_CONFIRM_BUTTON_SELECTOR}")
            await confirm_button_locator.click(timeout=CLICK_TIMEOUT_MS)
        else:
            self.logger.info(f"[{self.req_id}] 点击\"清空聊天\"按钮: {CLEAR_CHAT_BUTTON_SELECTOR}")
            await clear_chat_button_locator.click(timeout=CLICK_TIMEOUT_MS)
            await self._check_disconnect(check_client_disconnected, "清空聊天 - 点击\"清空聊天\"后")

            try:
                self.logger.info(f"[{self.req_id}] 等待清空聊天确认遮罩层出现: {OVERLAY_SELECTOR}")
                await expect_async(overlay_locator).to_be_visible(timeout=WAIT_FOR_ELEMENT_TIMEOUT_MS)
                self.logger.info(f"[{self.req_id}] 清空聊天确认遮罩层已出现。")
            except TimeoutError:
                error_msg = f"等待清空聊天确认遮罩层超时 (点击清空按钮后)。请求 ID: {self.req_id}"
                self.logger.error(error_msg)
                await save_error_snapshot(f"clear_chat_overlay_timeout_{self.req_id}")
                raise Exception(error_msg)

            await self._check_disconnect(check_client_disconnected, "清空聊天 - 遮罩层出现后")
            self.logger.info(f"[{self.req_id}] 点击\"继续\"按钮 (在对话框中): {CLEAR_CHAT_CONFIRM_BUTTON_SELECTOR}")
            await confirm_button_locator.click(timeout=CLICK_TIMEOUT_MS)

        await self._check_disconnect(check_client_disconnected, "清空聊天 - 点击\"继续\"后")

        # 等待对话框消失
        max_retries_disappear = 3
        for attempt_disappear in range(max_retries_disappear):
            try:
                self.logger.info(f"[{self.req_id}] 等待清空聊天确认按钮/对话框消失 (尝试 {attempt_disappear + 1}/{max_retries_disappear})...")
                await expect_async(confirm_button_locator).to_be_hidden(timeout=CLEAR_CHAT_VERIFY_TIMEOUT_MS)
                await expect_async(overlay_locator).to_be_hidden(timeout=1000)
                self.logger.info(f"[{self.req_id}] ✅ 清空聊天确认对话框已成功消失。")
                break
            except TimeoutError:
                self.logger.warning(f"[{self.req_id}] ⚠️ 等待清空聊天确认对话框消失超时 (尝试 {attempt_disappear + 1}/{max_retries_disappear})。")
                if attempt_disappear < max_retries_disappear - 1:
                    await asyncio.sleep(1.0)
                    await self._check_disconnect(check_client_disconnected, f"清空聊天 - 重试消失检查 {attempt_disappear + 1} 前")
                    continue
                else:
                    error_msg = f"达到最大重试次数。清空聊天确认对话框未消失。请求 ID: {self.req_id}"
                    self.logger.error(error_msg)
                    await save_error_snapshot(f"clear_chat_dialog_disappear_timeout_{self.req_id}")
                    raise Exception(error_msg)
            except ClientDisconnectedError:
                self.logger.info(f"[{self.req_id}] 客户端在等待清空确认对话框消失时断开连接。")
                raise
            except Exception as other_err:
                self.logger.warning(f"[{self.req_id}] 等待清空确认对话框消失时发生其他错误: {other_err}")
                if attempt_disappear < max_retries_disappear - 1:
                    await asyncio.sleep(1.0)
                    continue
                else:
                    raise

            await self._check_disconnect(check_client_disconnected, f"清空聊天 - 消失检查尝试 {attempt_disappear + 1} 后")

    async def _verify_chat_cleared(self, check_client_disconnected: Callable):
        """验证聊天已清空"""
        last_response_container = self.page.locator(RESPONSE_CONTAINER_SELECTOR).last
        await asyncio.sleep(0.5)
        await self._check_disconnect(check_client_disconnected, "After Clear Post-Delay")
        try:
            await expect_async(last_response_container).to_be_hidden(timeout=CLEAR_CHAT_VERIFY_TIMEOUT_MS - 500)
            self.logger.info(f"[{self.req_id}] ✅ 聊天已成功清空 (验证通过 - 最后响应容器隐藏)。")
        except Exception as verify_err:
            self.logger.warning(f"[{self.req_id}] ⚠️ 警告: 清空聊天验证失败 (最后响应容器未隐藏): {verify_err}")
    
    async def submit_prompt(self, prompt: str,image_list: List, check_client_disconnected: Callable):
        """提交提示到页面。"""
        self.logger.info(f"[{self.req_id}] 填充并提交提示 ({len(prompt)} chars)...")
        
        # 使用智能选择器获取正确的文本框
        prompt_textarea_locator = await self._get_prompt_textarea_locator()
        autosize_wrapper_locator = self.page.locator('ms-prompt-input-wrapper ms-autosize-textarea')
        submit_button_locator = self.page.locator(SUBMIT_BUTTON_SELECTOR)

        try:
            await expect_async(prompt_textarea_locator).to_be_visible(timeout=5000)
            await self._check_disconnect(check_client_disconnected, "After Input Visible")

            # 使用高效的人性化输入（保留随机字符但提高主要内容填充速度）
            await self._humanized_input(prompt_textarea_locator, prompt, check_client_disconnected)
            
            # 尝试设置autosize属性，如果失败则跳过
            try:
                await autosize_wrapper_locator.evaluate('(element, text) => { element.setAttribute("data-value", text); }', prompt)
            except Exception as attr_err:
                self.logger.warning(f"[{self.req_id}] 设置autosize属性失败，继续执行: {attr_err}")
            
            await self._check_disconnect(check_client_disconnected, "After Input Fill")

            # 上传
            if len(image_list) > 0:
                try:
                    # 1. 监听文件选择器
                    #    page.expect_file_chooser() 会返回一个上下文管理器
                    #    当文件选择器出现时，它会得到 FileChooser 对象
                    function_btn_localtor = self.page.locator('button[aria-label="Insert assets such as images, videos, files, or audio"]')
                    await function_btn_localtor.click()
                    #asyncio.sleep(0.5)
                    async with self.page.expect_file_chooser() as fc_info:
                        # 2. 点击那个会触发文件选择的普通按钮
                        upload_btn_localtor = self.page.locator(UPLOAD_BUTTON_SELECTOR)
                        await upload_btn_localtor.click()
                        print("点击了 JS 上传按钮，等待文件选择器...")

                    # 3. 获取文件选择器对象
                    file_chooser = await fc_info.value
                    print("文件选择器已出现。")

                    # 4. 设置要上传的文件
                    await file_chooser.set_files(image_list)
                    print(f"已将 '{image_list}' 设置到文件选择器。")

                    #asyncio.sleep(0.2)
                    acknow_btn_locator = self.page.locator('button[aria-label="Agree to the copyright acknowledgement"]')
                    if await acknow_btn_locator.count() > 0:
                        await acknow_btn_locator.click()

                except Exception as e:
                    print(f"在上传文件时发生错误: {e}")

            # 等待发送按钮启用
            wait_timeout_ms_submit_enabled = 100000
            try:
                await self._check_disconnect(check_client_disconnected, "填充提示后等待发送按钮启用 - 前置检查")
                await expect_async(submit_button_locator).to_be_enabled(timeout=wait_timeout_ms_submit_enabled)
                self.logger.info(f"[{self.req_id}] ✅ 发送按钮已启用。")
            except Exception as e_pw_enabled:
                self.logger.error(f"[{self.req_id}] ❌ 等待发送按钮启用超时或错误: {e_pw_enabled}")
                await save_error_snapshot(f"submit_button_enable_timeout_{self.req_id}")
                raise

            await self._check_disconnect(check_client_disconnected, "After Submit Button Enabled")
            await asyncio.sleep(0.3)

            # 尝试使用快捷键提交
            submitted_successfully = await self._try_shortcut_submit(prompt_textarea_locator, check_client_disconnected)

            # 如果快捷键失败，使用按钮点击
            if not submitted_successfully:
                self.logger.info(f"[{self.req_id}] 快捷键提交失败，尝试点击提交按钮...")
                try:
                    await submit_button_locator.click(timeout=5000)
                    self.logger.info(f"[{self.req_id}] ✅ 提交按钮点击完成。")
                except Exception as click_err:
                    self.logger.error(f"[{self.req_id}] ❌ 提交按钮点击失败: {click_err}")
                    await save_error_snapshot(f"submit_button_click_fail_{self.req_id}")
                    raise

            await self._check_disconnect(check_client_disconnected, "After Submit")
            
            # 检查是否有quota错误
            await self._check_quota_error_after_submit(check_client_disconnected)

        except Exception as e_input_submit:
            self.logger.error(f"[{self.req_id}] 输入和提交过程中发生错误: {e_input_submit}")
            if not isinstance(e_input_submit, ClientDisconnectedError):
                await save_error_snapshot(f"input_submit_error_{self.req_id}")
            raise

    async def _try_shortcut_submit(self, prompt_textarea_locator, check_client_disconnected: Callable) -> bool:
        """尝试使用快捷键提交"""
        import os
        try:
            # 检测操作系统
            host_os_from_launcher = os.environ.get('HOST_OS_FOR_SHORTCUT')
            is_mac_determined = False

            if host_os_from_launcher == "Darwin":
                is_mac_determined = True
            elif host_os_from_launcher in ["Windows", "Linux"]:
                is_mac_determined = False
            else:
                # 使用浏览器检测
                try:
                    user_agent_data_platform = await self.page.evaluate("() => navigator.userAgentData?.platform || ''")
                except Exception:
                    user_agent_string = await self.page.evaluate("() => navigator.userAgent || ''")
                    user_agent_string_lower = user_agent_string.lower()
                    if "macintosh" in user_agent_string_lower or "mac os x" in user_agent_string_lower:
                        user_agent_data_platform = "macOS"
                    else:
                        user_agent_data_platform = "Other"

                is_mac_determined = "mac" in user_agent_data_platform.lower()

            # 根据Mac系统和流式模式选择快捷键
            if is_mac_determined:
                if self.is_streaming:
                    shortcut_modifier = "Meta"  # Cmd+Enter for streaming mode on Mac
                else:
                    shortcut_modifier = "Alt"   # Option+Enter for non-streaming mode on Mac
            else:
                shortcut_modifier = "Control"  # Ctrl+Enter for Windows/Linux
            
            shortcut_key = "Enter"

            mode_desc = "流式" if self.is_streaming else "非流式"
            self.logger.info(f"[{self.req_id}] 使用快捷键: {shortcut_modifier}+{shortcut_key} ({mode_desc}模式)")

            await prompt_textarea_locator.focus(timeout=5000)
            await self._check_disconnect(check_client_disconnected, "After Input Focus")
            await asyncio.sleep(0.1)

            # 记录提交前的输入框内容，用于验证
            original_content = ""
            try:
                original_content = await prompt_textarea_locator.input_value(timeout=2000) or ""
            except Exception:
                # 如果无法获取原始内容，仍然尝试提交
                pass

            try:
                await self.page.keyboard.press(f'{shortcut_modifier}+{shortcut_key}')
            except Exception:
                # 尝试分步按键
                await self.page.keyboard.down(shortcut_modifier)
                await asyncio.sleep(0.05)
                await self.page.keyboard.press(shortcut_key)
                await asyncio.sleep(0.05)
                await self.page.keyboard.up(shortcut_modifier)

            await self._check_disconnect(check_client_disconnected, "After Shortcut Press")

            # 等待更长时间让提交完成
            await asyncio.sleep(2.0)

            # 多种方式验证提交是否成功
            submission_success = False

            try:
                # 方法1: 检查原始输入框是否清空
                current_content = await prompt_textarea_locator.input_value(timeout=2000) or ""
                if original_content and not current_content.strip():
                    self.logger.info(f"[{self.req_id}] 验证方法1: 输入框已清空，快捷键提交成功")
                    submission_success = True

                # 方法2: 检查提交按钮状态
                if not submission_success:
                    submit_button_locator = self.page.locator(SUBMIT_BUTTON_SELECTOR)
                    try:
                        is_disabled = await submit_button_locator.is_disabled(timeout=2000)
                        if is_disabled:
                            self.logger.info(f"[{self.req_id}] 验证方法2: 提交按钮已禁用，快捷键提交成功")
                            submission_success = True
                    except Exception:
                        pass

                # 方法3: 检查是否有响应容器出现
                if not submission_success:
                    try:
                        response_container = self.page.locator(RESPONSE_CONTAINER_SELECTOR)
                        container_count = await response_container.count()
                        if container_count > 0:
                            # 检查最后一个容器是否是新的
                            last_container = response_container.last
                            if await last_container.is_visible(timeout=1000):
                                self.logger.info(f"[{self.req_id}] 验证方法3: 检测到响应容器，快捷键提交成功")
                                submission_success = True
                    except Exception:
                        pass

            except Exception as verify_err:
                self.logger.warning(f"[{self.req_id}] 快捷键提交验证过程出错: {verify_err}")
                # 出错时假定提交成功，让后续流程继续
                submission_success = True

            if submission_success:
                self.logger.info(f"[{self.req_id}] ✅ 快捷键提交成功")
                return True
            else:
                self.logger.warning(f"[{self.req_id}] ⚠️ 快捷键提交验证失败")
                return False

        except Exception as shortcut_err:
            self.logger.warning(f"[{self.req_id}] 快捷键提交失败: {shortcut_err}")
            return False

    async def get_response(self, check_client_disconnected: Callable) -> str:
        """获取响应内容。"""
        self.logger.info(f"[{self.req_id}] 等待并获取响应...")

        try:
            # 等待响应容器出现
            response_container_locator = self.page.locator(RESPONSE_CONTAINER_SELECTOR).last
            response_element_locator = response_container_locator.locator(RESPONSE_TEXT_SELECTOR)

            self.logger.info(f"[{self.req_id}] 等待响应元素附加到DOM...")
            await expect_async(response_element_locator).to_be_attached(timeout=90000)
            await self._check_disconnect(check_client_disconnected, "获取响应 - 响应元素已附加")

            # 等待响应完成
            submit_button_locator = self.page.locator(SUBMIT_BUTTON_SELECTOR)
            edit_button_locator = self.page.locator(EDIT_MESSAGE_BUTTON_SELECTOR)
            input_field_locator = self.page.locator(PROMPT_TEXTAREA_SELECTOR)

            self.logger.info(f"[{self.req_id}] 等待响应完成...")
            completion_detected = await _wait_for_response_completion(
                self.page, input_field_locator, submit_button_locator, edit_button_locator, self.req_id, check_client_disconnected, None
            )

            if not completion_detected:
                self.logger.warning(f"[{self.req_id}] 响应完成检测失败，尝试获取当前内容")
            else:
                self.logger.info(f"[{self.req_id}] ✅ 响应完成检测成功")

            # 获取最终响应内容
            final_content = await _get_final_response_content(self.page, self.req_id, check_client_disconnected)

            if not final_content or not final_content.strip():
                self.logger.warning(f"[{self.req_id}] ⚠️ 获取到的响应内容为空")
                await save_error_snapshot(f"empty_response_{self.req_id}")
                # 不抛出异常，返回空内容让上层处理
                return ""

            self.logger.info(f"[{self.req_id}] ✅ 成功获取响应内容 ({len(final_content)} chars)")
            return final_content

        except Exception as e:
            self.logger.error(f"[{self.req_id}] ❌ 获取响应时出错: {e}")
            if not isinstance(e, ClientDisconnectedError):
                await save_error_snapshot(f"get_response_error_{self.req_id}")
            raise
    
    async def _check_quota_error_after_submit(self, check_client_disconnected: Callable) -> None:
        """提交后检查quota错误并处理降级"""
        try:
            from browser_utils.operations import detect_quota_error
            from config.model_fallback import model_fallback_manager
            import server
            
            # 等待一小段时间让错误元素显示
            await asyncio.sleep(0.5)
            
            # 检测quota错误
            has_quota_error, error_message = await detect_quota_error(self.page, self.req_id)
            
            if has_quota_error:
                self.logger.warning(f"[{self.req_id}] 检测到quota错误: {error_message}")
                
                # 获取当前实例ID和模型ID
                instance_id = str(getattr(server, 'current_instance_id', 1))
                current_model = getattr(server, 'current_ai_studio_model_id', None)
                
                if current_model:
                    # 标记模型为不可用
                    model_fallback_manager.mark_model_quota_exceeded(
                        instance_id, current_model, error_message
                    )
                    
                    # 尝试获取降级模型
                    fallback_model = model_fallback_manager.get_fallback_model(
                        instance_id, current_model
                    )
                    
                    if fallback_model and fallback_model != current_model:
                        self.logger.info(f"[{self.req_id}] 尝试降级到模型: {fallback_model}")
                        
                        # 抛出quota错误异常，让上层处理重试
                        from api_utils.exceptions import QuotaExceededException
                        raise QuotaExceededException(
                            f"Model {current_model} quota exceeded. Fallback to {fallback_model}",
                            original_model=current_model,
                            fallback_model=fallback_model,
                            instance_id=instance_id
                        )
                    else:
                        # 没有可用的降级模型
                        self.logger.error(f"[{self.req_id}] 无可用的降级模型")
                        raise HTTPException(
                            status_code=429,
                            detail=f"Rate limit exceeded for model {current_model} and no fallback available"
                        )
                        
        except Exception as e:
            # 如果不是quota相关的异常，记录但不阻止正常流程
            if not isinstance(e, (QuotaExceededException, HTTPException)):
                self.logger.debug(f"[{self.req_id}] Quota检查时出错: {e}")
            else:
                raise
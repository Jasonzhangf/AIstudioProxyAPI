"""
人性化输入模拟模块
实现更自然的人类输入行为，避免被检测为机器人
"""
import asyncio
import random
import string
from typing import List
from playwright.async_api import Locator

class HumanInputSimulator:
    """模拟人类输入行为的工具类"""
    
    # 常见的随机单词列表
    RANDOM_WORDS = [
        "hello", "world", "test", "check", "yes", "no", "ok", "good", "nice", "great",
        "sure", "maybe", "think", "know", "see", "look", "try", "help", "work", "time",
        "what", "how", "when", "where", "why", "can", "will", "should", "could", "would",
        "the", "and", "or", "but", "so", "if", "then", "now", "here", "there",
        "this", "that", "these", "those", "some", "any", "all", "more", "most", "many"
    ]
    
    def __init__(self, logger=None):
        self.logger = logger
    
    def _log(self, message: str):
        """日志记录"""
        if self.logger:
            self.logger.debug(f"[HumanInput] {message}")
    
    async def _random_delay(self, min_ms: int = 50, max_ms: int = 200):
        """随机延迟，模拟人类反应时间"""
        delay = random.randint(min_ms, max_ms) / 1000.0
        await asyncio.sleep(delay)
    
    async def _typing_delay(self, char_count: int = 1):
        """打字延迟，根据字符数量调整"""
        # 基础延迟 + 每个字符的延迟
        base_delay = random.randint(30, 80) / 1000.0
        char_delay = char_count * random.randint(10, 30) / 1000.0
        total_delay = base_delay + char_delay
        await asyncio.sleep(total_delay)
    
    def _generate_random_text(self, word_count: int = None) -> str:
        """生成随机文本"""
        if word_count is None:
            word_count = random.randint(2, 5)
        
        words = random.sample(self.RANDOM_WORDS, min(word_count, len(self.RANDOM_WORDS)))
        return " ".join(words)
    
    def _generate_typo_text(self, original: str) -> str:
        """生成包含打字错误的文本"""
        if len(original) < 3:
            return original
        
        # 随机选择一个位置插入错误字符
        pos = random.randint(1, len(original) - 1)
        error_char = random.choice(string.ascii_lowercase)
        return original[:pos] + error_char + original[pos:]
    
    async def simulate_pre_input_behavior(self, textarea_locator: Locator):
        """模拟输入前的行为：随机输入一些单词然后删除"""
        try:
            self._log("开始模拟输入前行为...")
            
            # 确保文本框获得焦点
            await textarea_locator.click()
            await self._random_delay(100, 300)
            
            # 生成随机文本
            random_text = self._generate_random_text(random.randint(2, 4))
            self._log(f"输入随机文本: '{random_text}'")
            
            # 逐字符输入
            for char in random_text:
                await textarea_locator.type(char)
                await self._typing_delay()
            
            # 随机暂停，模拟思考
            await self._random_delay(500, 1500)
            
            # 删除所有文本
            self._log("删除随机文本...")
            await textarea_locator.press("Control+a")  # 全选
            await self._random_delay(50, 150)
            await textarea_locator.press("Delete")  # 删除
            await self._random_delay(200, 500)
            
            self._log("输入前行为模拟完成")
            
        except Exception as e:
            self._log(f"输入前行为模拟失败: {e}")
            # 不抛出异常，避免影响主要功能
    
    async def simulate_human_typing(self, textarea_locator: Locator, text: str, enable_typos: bool = True):
        """模拟人类打字行为"""
        try:
            self._log(f"开始模拟人类打字: {len(text)} 字符")
            
            if not text:
                return
            
            # 分段输入，模拟思考停顿
            words = text.split()
            current_text = ""
            
            for i, word in enumerate(words):
                # 添加空格（除了第一个单词）
                if i > 0:
                    current_text += " "
                    await textarea_locator.type(" ")
                    await self._typing_delay()
                
                # 模拟打字错误和修正
                if enable_typos and len(word) > 3 and random.random() < 0.1:  # 10% 概率打错
                    # 输入错误版本
                    typo_word = self._generate_typo_text(word)
                    self._log(f"模拟打字错误: '{word}' -> '{typo_word}'")
                    
                    for char in typo_word:
                        await textarea_locator.type(char)
                        await self._typing_delay()
                    
                    # 暂停，发现错误
                    await self._random_delay(300, 800)
                    
                    # 删除错误并重新输入
                    for _ in range(len(typo_word)):
                        await textarea_locator.press("Backspace")
                        await self._typing_delay()
                    
                    await self._random_delay(100, 300)
                
                # 正常输入单词
                for char in word:
                    await textarea_locator.type(char)
                    await self._typing_delay()
                
                current_text += word
                
                # 在句子结束处暂停
                if word.endswith(('.', '!', '?', '。', '！', '？')):
                    await self._random_delay(800, 1500)
                elif word.endswith((',', '，')):
                    await self._random_delay(300, 600)
                elif i < len(words) - 1:  # 单词间的正常停顿
                    await self._random_delay(100, 400)
            
            self._log("人类打字模拟完成")
            
        except Exception as e:
            self._log(f"人类打字模拟失败: {e}")
            # 如果模拟失败，回退到直接填充
            await self._fallback_to_direct_fill(textarea_locator, text)
    
    async def simulate_post_input_behavior(self, textarea_locator: Locator):
        """模拟输入后的行为：光标移动、检查等"""
        try:
            self._log("开始模拟输入后行为...")
            
            # 随机移动光标到文本末尾
            await textarea_locator.press("End")
            await self._random_delay(100, 300)
            
            # 模拟检查输入的行为
            check_behaviors = [
                lambda: textarea_locator.press("Home"),  # 移动到开头
                lambda: textarea_locator.press("End"),   # 移动到结尾
                lambda: self._random_delay(200, 500),    # 简单停顿
            ]
            
            # 随机选择1-2个检查行为
            selected_behaviors = random.sample(check_behaviors, random.randint(1, 2))
            for behavior in selected_behaviors:
                await behavior()
                await self._random_delay(100, 300)
            
            # 最终确保光标在文本末尾
            await textarea_locator.press("End")
            await self._random_delay(200, 500)
            
            self._log("输入后行为模拟完成")
            
        except Exception as e:
            self._log(f"输入后行为模拟失败: {e}")
            # 不抛出异常，避免影响主要功能
    
    async def _fallback_to_direct_fill(self, textarea_locator: Locator, text: str):
        """回退到直接填充文本的方法"""
        self._log("回退到直接填充模式")
        try:
            await textarea_locator.fill(text)
        except Exception as e:
            self._log(f"直接填充也失败: {e}")
            # 使用最基础的JavaScript填充
            await textarea_locator.evaluate(
                '''
                (element, text) => {
                    element.value = text;
                    element.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
                    element.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
                }
                ''',
                text
            )
    
    async def human_like_input(self, textarea_locator: Locator, text: str, 
                              enable_pre_behavior: bool = True,
                              enable_typing_simulation: bool = True,
                              enable_post_behavior: bool = True,
                              enable_typos: bool = True):
        """
        完整的人性化输入流程
        
        Args:
            textarea_locator: 文本区域定位器
            text: 要输入的文本
            enable_pre_behavior: 是否启用输入前行为模拟
            enable_typing_simulation: 是否启用打字模拟
            enable_post_behavior: 是否启用输入后行为模拟
            enable_typos: 是否启用打字错误模拟
        """
        try:
            self._log(f"开始人性化输入流程: {len(text)} 字符")
            
            # 1. 输入前行为模拟
            if enable_pre_behavior and len(text) > 50:  # 只对长文本进行预输入模拟
                await self.simulate_pre_input_behavior(textarea_locator)
            
            # 2. 主要文本输入
            if enable_typing_simulation and len(text) <= 500:  # 只对中等长度文本进行逐字输入
                await self.simulate_human_typing(textarea_locator, text, enable_typos)
            else:
                # 对于很长的文本，直接填充但添加一些延迟
                self._log("文本过长，使用优化的直接填充模式")
                await self._fallback_to_direct_fill(textarea_locator, text)
                await self._random_delay(500, 1000)
            
            # 3. 输入后行为模拟
            if enable_post_behavior:
                await self.simulate_post_input_behavior(textarea_locator)
            
            self._log("人性化输入流程完成")
            
        except Exception as e:
            self._log(f"人性化输入流程失败: {e}")
            # 最终回退方案
            await self._fallback_to_direct_fill(textarea_locator, text)
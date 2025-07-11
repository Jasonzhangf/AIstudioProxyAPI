"""
CSS选择器配置模块
包含所有用于页面元素定位的CSS选择器
"""

# --- 输入相关选择器 ---
# 主选择器：使用更精确的选择器避免匹配多个元素
PROMPT_TEXTAREA_SELECTOR = 'textarea[aria-label="Type something or tab to choose an example prompt"]'
# 备用选择器1：另一种aria-label格式
PROMPT_TEXTAREA_SELECTOR_ALT = 'textarea[aria-label="Start typing a prompt"]'
# 备用选择器2：通用容器选择器
PROMPT_TEXTAREA_SELECTOR_ALT2 = '.prompt-input-wrapper-container textarea'
INPUT_SELECTOR = PROMPT_TEXTAREA_SELECTOR
INPUT_SELECTOR2 = PROMPT_TEXTAREA_SELECTOR

# --- 按钮选择器 ---
SUBMIT_BUTTON_SELECTOR = 'button[aria-label="Run"].run-button'
CLEAR_CHAT_BUTTON_SELECTOR = 'button[data-test-clear="outside"][aria-label="Clear chat"]'
CLEAR_CHAT_CONFIRM_BUTTON_SELECTOR = 'button.mdc-button:has-text("Continue")'
UPLOAD_BUTTON_SELECTOR = 'button[aria-label="Upload File"]'

# --- 响应相关选择器 ---
RESPONSE_CONTAINER_SELECTOR = 'ms-chat-turn .chat-turn-container.model'
RESPONSE_TEXT_SELECTOR = 'ms-cmark-node.cmark-node'

# --- 加载和状态选择器 ---
LOADING_SPINNER_SELECTOR = 'button[aria-label="Run"].run-button svg .stoppable-spinner'
OVERLAY_SELECTOR = 'div.cdk-overlay-backdrop'

# --- 错误提示选择器 ---
ERROR_TOAST_SELECTOR = 'div.toast.warning, div.toast.error'
MODEL_ERROR_SELECTOR = 'div.model-error'
RATE_LIMIT_ERROR_SELECTOR = 'div.model-error mat-icon[role="img"]:has-text("error")'

# --- 编辑相关选择器 ---
EDIT_MESSAGE_BUTTON_SELECTOR = 'ms-chat-turn:last-child .actions-container button.toggle-edit-button'
MESSAGE_TEXTAREA_SELECTOR = 'ms-chat-turn:last-child ms-text-chunk ms-autosize-textarea'
FINISH_EDIT_BUTTON_SELECTOR = 'ms-chat-turn:last-child .actions-container button.toggle-edit-button[aria-label="Stop editing"]'

# --- 菜单和复制相关选择器 ---
MORE_OPTIONS_BUTTON_SELECTOR = 'div.actions-container div ms-chat-turn-options div > button'
COPY_MARKDOWN_BUTTON_SELECTOR = 'button.mat-mdc-menu-item:nth-child(4)'
COPY_MARKDOWN_BUTTON_SELECTOR_ALT = 'div[role="menu"] button:has-text("Copy Markdown")'

# --- 设置相关选择器 ---
MAX_OUTPUT_TOKENS_SELECTOR = 'input[aria-label="Maximum output tokens"]'
STOP_SEQUENCE_INPUT_SELECTOR = 'input[aria-label="Add stop token"]'
MAT_CHIP_REMOVE_BUTTON_SELECTOR = 'mat-chip-set mat-chip-row button[aria-label*="Remove"]'
TOP_P_INPUT_SELECTOR = 'div.settings-item-column:has(h3:text-is("Top P")) input[type="number"].slider-input'
TEMPERATURE_INPUT_SELECTOR = 'div[data-test-id="temperatureSliderContainer"] input[type="number"].slider-input'
USE_URL_CONTEXT_SELECTOR = 'button[aria-label="Browse the url context"]'
SET_THINKING_BUDGET_TOGGLE_SELECTOR = 'button[aria-label="Toggle thinking budget between auto and manual"]'
# Thinking budget slider input
THINKING_BUDGET_INPUT_SELECTOR = '//div[contains(@class, "settings-item") and .//p[normalize-space()="Set thinking budget"]]/following-sibling::div//input[@type="number"]'
# --- Google Search Grounding ---
GROUNDING_WITH_GOOGLE_SEARCH_TOGGLE_SELECTOR = 'div[data-test-id="searchAsAToolTooltip"] mat-slide-toggle button'
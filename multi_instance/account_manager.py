import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional


class AccountManager:
    """
    账号管理器，负责加载和管理多个auth文件
    """
    
    def __init__(self, auth_dir: str = "auth_profiles", logger: Optional[logging.Logger] = None):
        self.auth_dir = Path(auth_dir)
        self.accounts: Dict[str, dict] = {}
        self.logger = logger or logging.getLogger(__name__)
        self.load_accounts()
    
    def load_accounts(self):
        """
        加载所有auth文件
        """
        if not self.auth_dir.exists():
            self.logger.warning(f"Auth directory {self.auth_dir} does not exist")
            return
        
        # 先清空现有账号
        self.accounts.clear()
        
        # 加载multi目录下的账号
        multi_dir = self.auth_dir / "multi"
        if multi_dir.exists():
            for auth_file in multi_dir.glob("*.json"):
                self._load_account_file(auth_file)
        
        # 如果multi目录没有账号，则加载根目录下的账号
        if not self.accounts:
            for auth_file in self.auth_dir.glob("*.json"):
                self._load_account_file(auth_file)
        
        self.logger.info(f"Loaded {self.get_account_count()} accounts")
    
    def _load_account_file(self, auth_file: Path):
        """
        加载单个账号文件
        """
        try:
            with open(auth_file, 'r', encoding='utf-8') as f:
                account_data = json.load(f)
                account_name = auth_file.stem
                self.accounts[account_name] = account_data
                self.logger.debug(f"Loaded account: {account_name} from {auth_file}")
        except Exception as e:
            self.logger.error(f"Error loading account from {auth_file}: {e}")
    
    def get_account(self, account_name: str) -> dict:
        """
        获取指定账号的配置
        """
        return self.accounts.get(account_name, {})
    
    def list_accounts(self) -> List[str]:
        """
        列出所有账号名称
        """
        return list(self.accounts.keys())
    
    def get_account_count(self) -> int:
        """
        获取账号数量
        """
        return len(self.accounts)
    
    def get_account_email(self, account_name: str) -> Optional[str]:
        """
        获取账号的邮箱地址
        """
        account = self.get_account(account_name)
        return account.get('email', account_name) if account else None
    
    def refresh_accounts(self):
        """
        刷新账号列表
        """
        self.logger.info("Refreshing accounts")
        self.load_accounts()
    
    def account_exists(self, account_name: str) -> bool:
        """
        检查账号是否存在
        """
        return account_name in self.accounts
    
    def get_accounts_by_domain(self, domain: str) -> List[str]:
        """
        根据域名筛选账号
        """
        matching_accounts = []
        for account_name, account_data in self.accounts.items():
            email = account_data.get('email', account_name)
            if domain in email:
                matching_accounts.append(account_name)
        return matching_accounts


if __name__ == "__main__":
    # 测试账号管理器
    logging.basicConfig(level=logging.INFO)
    account_manager = AccountManager()
    print(f"Loaded {account_manager.get_account_count()} accounts:")
    for account in account_manager.list_accounts():
        print(f"  - {account} ({account_manager.get_account_email(account)})")
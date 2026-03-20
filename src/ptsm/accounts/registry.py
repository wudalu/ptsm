from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ACCOUNT_ROOT = PACKAGE_ROOT / "accounts" / "definitions"


@dataclass(frozen=True)
class AccountProfile:
    """Local account profile used to scope a playbook run."""

    account_id: str
    nickname: str
    platform: str
    domain: str
    publish_mode: str = "dry-run"
    source_path: Path | None = None

    def to_dict(self) -> dict[str, str]:
        return {
            "account_id": self.account_id,
            "nickname": self.nickname,
            "platform": self.platform,
            "domain": self.domain,
            "publish_mode": self.publish_mode,
        }


class AccountRegistry:
    """Discover account definitions from local YAML files."""

    def __init__(self, account_root: Path | None = None):
        self.account_root = account_root or ACCOUNT_ROOT
        self._accounts = self._load_accounts()

    def get(self, account_id: str) -> AccountProfile:
        for account in self._accounts:
            if account.account_id == account_id:
                return account
        raise LookupError(f"Unknown account: {account_id}")

    def list_accounts(self) -> list[AccountProfile]:
        return list(self._accounts)

    def _load_accounts(self) -> list[AccountProfile]:
        accounts: list[AccountProfile] = []
        for path in sorted(self.account_root.rglob("*.yaml")):
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            accounts.append(
                AccountProfile(
                    account_id=payload["account_id"],
                    nickname=payload["nickname"],
                    platform=payload["platform"],
                    domain=payload["domain"],
                    publish_mode=payload.get("publish_mode", "dry-run"),
                    source_path=path,
                )
            )
        return accounts

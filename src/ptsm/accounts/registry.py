from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ACCOUNT_ROOT = PACKAGE_ROOT / "accounts" / "definitions"


@dataclass(frozen=True)
class AccountProfile:
    """Local account profile with optional cookie profile for multi-account isolation."""

    account_id: str
    nickname: str
    platform: str
    domain: str
    publish_mode: str = "dry-run"
    cookie_profile_id: str = ""
    cookie_path: str = ""
    publisher_server_url: str = ""
    publisher_visibility: str = ""
    source_path: Path | None = None

    @property
    def has_cookie_profile(self) -> bool:
        return bool(self.cookie_profile_id and self.cookie_path)

    def to_dict(self) -> dict[str, str]:
        d = {
            "account_id": self.account_id,
            "nickname": self.nickname,
            "platform": self.platform,
            "domain": self.domain,
            "publish_mode": self.publish_mode,
        }
        if self.cookie_profile_id:
            d["cookie_profile_id"] = self.cookie_profile_id
            d["cookie_path"] = self.cookie_path
        if self.publisher_server_url:
            d["publisher_server_url"] = self.publisher_server_url
        return d


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
                    cookie_profile_id=str(payload.get("cookie_profile_id", "")),
                    cookie_path=str(payload.get("cookie_path", "")),
                    publisher_server_url=str(payload.get("publisher_server_url", "")),
                    publisher_visibility=str(payload.get("publisher_visibility", "")),
                    source_path=path,
                )
            )
        return accounts

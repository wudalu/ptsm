from __future__ import annotations

import builtins
import importlib
import sys


def test_publisher_module_import_does_not_require_langchain_mcp_adapter(
    monkeypatch,
) -> None:
    sys.modules.pop("ptsm.infrastructure.publishers.xiaohongshu_mcp_publisher", None)
    original_import = builtins.__import__

    def guarded_import(name: str, *args, **kwargs):
        if name == "langchain_mcp_adapters.client":
            raise ImportError("blocked langchain mcp adapter import")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    module = importlib.import_module(
        "ptsm.infrastructure.publishers.xiaohongshu_mcp_publisher"
    )

    assert hasattr(module, "LangChainMcpToolRunner")

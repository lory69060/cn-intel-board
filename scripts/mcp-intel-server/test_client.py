#!/usr/bin/env python3
"""
MCP Intel Server 官方 SDK 客户端测试
验证：任何兼容 MCP 协议的 Agent（Claude/自建）都能调用我们的数据服务

用法：
  python3 -m venv /tmp/mcp-venv && /tmp/mcp-venv/bin/pip install mcp
  /tmp/mcp-venv/bin/python scripts/mcp-intel-server/test_client.py

输出：6 项协议测试（initialize / list_tools / call_tool 全量 / call_tool 筛选 / track_record / ask_edge）
"""
import asyncio, json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_ARGS = ["scripts/mcp-intel-server/server.py"]


async def main():
    params = StdioServerParameters(
        command="/usr/bin/python3",
        args=SERVER_ARGS,
        cwd="/Users/wangyifei/.openclaw/workspace",
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"✅ SDK initialize → server={init.server_info.name} v{init.server_info.version} 协议={init.protocol_version}")

            tools = await session.list_tools()
            print(f"✅ SDK list_tools → {len(tools.tools)} 个: {[t.name for t in tools.tools]}")

            res = await session.call_tool("read_signal_board", {})
            data = json.loads(res.content[0].text)
            print(f"✅ SDK call_tool 全量 → {data['total']} 条信号")

            res = await session.call_tool("read_signal_board", {"industry": "低空经济/eVTOL", "limit": 1})
            data = json.loads(res.content[0].text)
            if data["signals"]:
                title = data["signals"][0].get("signal", "")
                print(f"✅ SDK call_tool 筛选 → {data['total']} 条: {title[:50]}")

            res = await session.call_tool("get_track_record", {})
            data = json.loads(res.content[0].text)
            print(f"✅ SDK call_tool track_record → 总数 {data['summary']['total_signals']}, 已验证 {data['summary']['verified']}, 命中率 {data['summary']['hit_rate']}")

            res = await session.call_tool("ask_edge", {"question": "固态电池上游材料谁有信息差？", "limit": 2})
            data = json.loads(res.content[0].text)
            print(f"✅ SDK call_tool ask_edge → 检测行业 {data['detected_industry']}, 匹配 {data['total_matched']} 条")

            res = await session.call_tool("list_articles", {"limit": 3})
            data = json.loads(res.content[0].text)
            print(f"✅ SDK call_tool list_articles → {data['total']} 篇文章（展示{len(data['articles'])}篇）")

            res = await session.call_tool("read_article", {"title": "存储"})
            data = json.loads(res.content[0].text)
            print(f"✅ SDK call_tool read_article → {data['file']}（{len(data['content'])}字）")

            print("\n🎉 官方 SDK 客户端验证通过 — 任何兼容 MCP 的 Agent 都能直接调用我们的数据服务（含文章阅读工具）")


if __name__ == "__main__":
    asyncio.run(main())

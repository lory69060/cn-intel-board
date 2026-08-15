# China Supply Chain Intel — MCP Server

> 中国硬科技供应链信息差数据资产（Machine-readable China supply-chain intelligence）

MCP (Model Context Protocol) server exposing **China hard-tech supply chain intel** as structured, machine-readable data. Built for AI agents (DeepSeek Harness / Claude / any MCP client) that need verifiable China supply-chain signals — not news headlines.

## 📦 MCP Tools (4)

| Tool | Description |
|:-----|:------------|
| `read_signal_board` | 信号信息差看板 — 33 structured signals (storage/semiconductors, rare earth, EV, AI infra…). Each signal carries `predicted_on` / `verify_by` / `verify_event` / `result` — a **verifiable track record**, not just claims. |
| `get_track_record` | 信号命中率统计 — hit-rate analytics across all signals by industry. |
| `ask_edge` | 问答式信息差 — edge/contrarian intel on a topic (GLM-assisted, returns evidence + sources). |
| `read_earnings_tracker` | 2026 H1 earnings tracker — 7 companies' publicly disclosed results (akshare-verified, updated daily to 8/31). |

## 🚀 Quick Start

Pure Python stdlib, zero dependencies:

```bash
# list tools
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python3 scripts/mcp-intel-server/server.py

# call read_signal_board
echo '{"jsonrpc":"2.0","method":"tools/call","id":2,"params":{"name":"read_signal_board","arguments":{}}}' | python3 scripts/mcp-intel-server/server.py

# filter by industry
echo '{"jsonrpc":"2.0","method":"tools/call","id":3,"params":{"name":"read_signal_board","arguments":{"industry":"存储/半导体"}}}' | python3 scripts/mcp-intel-server/server.py
```

Or with any MCP client:

```json
{
  "mcpServers": {
    "cn-intel": {
      "command": "python3",
      "args": ["/path/to/scripts/mcp-intel-server/server.py"]
    }
  }
}
```

## 📊 Data Assets

- `data/public-content/signal-board-structured.json` — 33 signals with verification fields
- `data/earnings/2026-half-year/earnings-tracker.json` — 2026 H1 earnings tracker

## ⚠️ Compliance

Data is public-disclosure based; no buy/sell recommendations. For research and cross-verification only.

## 🔗 Related

- Web dashboard: https://lory69060.github.io/cn-intel-board/
- llms.txt: https://lory69060.github.io/cn-intel-board/llms.txt
- Part of the DeepSeek Harness (DSH) ecosystem — topic: `#dsh`

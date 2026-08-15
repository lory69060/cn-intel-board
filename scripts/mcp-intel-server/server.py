#!/usr/bin/env python3
"""
MCP Intel Server — 最小化 MCP 骨架（纯 stdlib，无需额外依赖）

功能：
  - read_signal_board()   读取信号信息差看板（可按行业筛选）
  - read_earnings_tracker() 读取中报信号验证追踪表
  - get_track_record()    读取信号验证记录（命中率/待验证清单）——护城河资产层
  - ask_edge()            问答式信息差查询（Agent 问一句，返回相关信号+信息差）

协议：MCP JSON-RPC over stdio（handle tools/list + tools/call）

依赖：
  pip install mcp        # 生产环境使用正式 MCP SDK
  当前实现：纯 stdlib，可零依赖运行

启动方式：
  python3 server.py      # 通过 stdio 与 MCP client 通信
"""

import json
import sys
import os
import traceback
from pathlib import Path
from typing import Optional

# ─── 配置 ────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent
SIGNAL_JSON = BASE_DIR / "data" / "public-content" / "signal-board-structured.json"
EARNINGS_JSON = BASE_DIR / "data" / "earnings" / "2026-half-year" / "earnings-tracker.json"
ARTICLES_DIR = BASE_DIR / "data" / "public-content" / "articles"

# ─── 工具定义（MCP tools/list 响应）────────────────────
TOOLS = [
    {
        "name": "read_signal_board",
        "description": "读取信号信息差看板，返回结构化 JSON，包含 📊 高信息差信号（真信息差）。每条信号含 predicted_on/verify_by/verify_event/result 验证记录字段。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "industry": {
                    "type": "string",
                    "description": "按行业筛选，如 '存储/半导体'、'固态电池'、'低空经济/eVTOL'、'创新药'；不填则返回全部"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回条数上限，默认全部"
                },
                "result": {
                    "type": "string",
                    "description": "按验证结果筛选：'待验证'/'已兑现'/'部分兑现'/'落空'/'推迟'；不填则返回全部"
                }
            },
            "required": []
        }
    },
    {
        "name": "read_earnings_tracker",
        "description": "读取中报信号验证追踪表：我们信号板预测的公司 vs 实际披露业绩 vs 验证状态（验证/部分验证/待验证）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "industry": {
                    "type": "string",
                    "description": "按行业筛选，如 '存储/半导体'、'储能/电池'；不填则返回全部"
                },
                "status": {
                    "type": "string",
                    "description": "按验证状态筛选：'验证'/'部分验证'/'待验证'；不填则返回全部"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_track_record",
        "description": "读取信号验证记录（track record）：命中率、已验证/待验证统计、每条信号从 predicted_on 到 verify_by 的结果。这是唯一用时间积累的资产——判断层的命中历史，LLM 无法生成。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "industry": {
                    "type": "string",
                    "description": "按行业筛选命中率统计；不填则返回全量"
                },
                "include_signals": {
                    "type": "boolean",
                    "description": "是否包含每条信号的明细，默认 true"
                }
            },
            "required": []
        }
    },
    {
        "name": "ask_edge",
        "description": "问答式信息差查询：Agent 用自然语言问产业问题，返回最相关的信号+信息差依据。区别于数据 API——返回的是判断层（what it means），不是原始数据。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "自然语言问题，如 '固态电池上游材料谁有信息差？'、'存储板块有什么散户不知道的？'"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回条数上限，默认 5"
                }
            },
            "required": ["question"]
        }
    },
    {
        "name": "list_articles",
        "description": "列出中国硬科技供应链研究文章清单（标题/主题/链接），供 Agent 发现可引用的深度内容。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "按主题筛选，如 '存储'、'AI'、'冷链'、'固态电池'；不填则返回全部"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回条数上限，默认 20"
                }
            },
            "required": []
        }
    },
    {
        "name": "read_article",
        "description": "读取指定研究文章全文（中文），供 Agent 引用分析。文章是我们对产业的一手调查笔记（信息差视角）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "文章标题或文件名（可用 list_articles 查看），支持模糊匹配"
                }
            },
            "required": ["title"]
        }
    }
]

# ─── 行业关键词映射（ask_edge 用）───────────────────────
# 专属词（行业名/公司名，权重 3）+ 通用词（材料/成本等跨行业词，权重 1）
INDUSTRY_KEYWORDS = {
    "存储/半导体": {
        "专属": ["存储", "半导体", "芯片", "HBM", "DRAM", "光刻", "刻蚀", "封装", "CoWoS", "长鑫", "台积电", "北方华创", "中微", "拓荆", "零部件", "耗材", "光刻胶"],
        "通用": ["材料", "国产率", "资本支出", "估值", "产能"],
    },
    "固态电池": {
        "专属": ["固态电池", "硫化物", "硫化锂", "锂金属", "电解质", "隔膜", "电芯", "比亚迪", "国轩", "恩捷", "清陶", "负极"],
        "通用": ["上游", "材料", "成本", "电池", "产能", "装车", "订单"],
    },
    "低空经济/eVTOL": {
        "专属": ["低空", "eVTOL", "飞行汽车", "无人机", "航电", "亿航", "峰飞", "沃兰特", "御风", "适航"],
        "通用": ["电池", "订单", "成本", "整机", "市场"],
    },
    "创新药": {
        "专属": ["创新药", "医药", "康方", "恒瑞", "GLP", "替尔泊肽", "CDMO", "商保", "医保", "BD交易", "管线", "临床"],
        "通用": ["交易", "出海", "支付", "目录"],
    },
}


def _detect_industry(question: str) -> Optional[str]:
    """问题 → 行业：专属词命中加权，返回得分最高的行业"""
    q = question.lower()
    best_ind, best_score = None, 0
    for ind, kws in INDUSTRY_KEYWORDS.items():
        score = 0
        for kw in kws.get("专属", []):
            if kw.lower() in q:
                score += 3
        for kw in kws.get("通用", []):
            if kw.lower() in q:
                score += 1
        if score > best_score:
            best_ind, best_score = ind, score
    return best_ind if best_score > 0 else None


def _score_question(question: str, signal: dict, detected: Optional[str]) -> int:
    """问答匹配打分：检测行业优先，内容关键词次之"""
    q = question.lower()
    score = 0
    ind = signal.get("industry", "")
    text = (signal.get("signal", "") + " " + signal.get("basis", "")).lower()

    # 行业优先：问题命中的行业 +6，其他行业不因泛词加分
    if detected and ind == detected:
        score += 6
    elif detected:
        return 0

    # 内容关键词命中 +1（取问题中的词）
    stopwords = {"什么", "怎么", "如何", "有", "是", "的", "了", "吗", "呢", "谁", "我们", "哪些", "一个", "这个", "那个", "散户", "市场", "信息差", "事情", "方面"}
    q_words = [w for w in q.replace("？", " ").replace("?", " ").replace("：", " ").split() if w and w not in stopwords]
    for w in q_words:
        if len(w) >= 2 and w in text:
            score += 1

    return score


# ─── 消息处理 ────────────────────────────────────────────
def _send(obj: dict) -> None:
    """写一条 JSON-RPC 响应到 stdout"""
    line = json.dumps(obj, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def handle_tools_list() -> dict:
    return {"tools": TOOLS}


def _read_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def handle_earnings_tracker(args: dict) -> dict:
    try:
        data = _read_json(EARNINGS_JSON)
        companies = data.get("tracked_companies", [])
        industry = args.get("industry")
        status = args.get("status")

        if industry:
            companies = [c for c in companies if industry in c.get("industry", "")]
        if status:
            companies = [c for c in companies if c.get("verification", {}).get("result", "") == status]

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {"total": len(companies), "tracked_companies": companies, "source": str(EARNINGS_JSON)},
                        ensure_ascii=False,
                        indent=2
                    )
                }
            ]
        }
    except Exception as e:
        return {"error": {"code": -32000, "message": str(e)}}


def handle_track_record(args: dict) -> dict:
    """命中率统计 + 验证记录明细"""
    try:
        data = _read_json(SIGNAL_JSON)
        signals = data.get("signals", [])
        industry = args.get("industry")
        include_signals = args.get("include_signals", True)

        if industry:
            signals = [s for s in signals if industry in s.get("industry", "")]

        total = len(signals)
        pending = [s for s in signals if s.get("result") == "待验证"]
        verified = [s for s in signals if s.get("result") in ("已兑现", "部分兑现", "落空")]
        hit = [s for s in verified if s.get("result") in ("已兑现", "部分兑现")]
        miss = [s for s in verified if s.get("result") == "落空"]
        delayed = [s for s in signals if s.get("result") == "推迟"]

        # 按行业聚合
        by_industry = {}
        for s in signals:
            ind = s.get("industry", "未知")
            b = by_industry.setdefault(ind, {"total": 0, "verified": 0, "hit": 0, "pending": 0})
            b["total"] += 1
            if s.get("result") == "待验证":
                b["pending"] += 1
            elif s.get("result") in ("已兑现", "部分兑现", "落空"):
                b["verified"] += 1
                if s.get("result") in ("已兑现", "部分兑现"):
                    b["hit"] += 1

        result = {
            "summary": {
                "total_signals": total,
                "pending": len(pending),
                "verified": len(verified),
                "hit": len(hit),
                "miss": len(miss),
                "delayed": len(delayed),
                "hit_rate": round(len(hit) / len(verified), 3) if verified else None,
                "note": "hit_rate = 已兑现+部分兑现 / 已验证；待验证不计入分母"
            },
            "by_industry": by_industry,
            "source": str(SIGNAL_JSON),
        }
        if include_signals:
            result["signals"] = signals

        return {
            "content": [
                {"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}
            ]
        }
    except Exception as e:
        return {"error": {"code": -32000, "message": str(e)}}


def handle_ask_edge(args: dict) -> dict:
    """问答式信息差：返回最相关信号 + 依据"""
    try:
        question = args.get("question", "")
        limit = int(args.get("limit", 5))
        if not question:
            return {"error": {"code": -32002, "message": "question 必填"}}

        data = _read_json(SIGNAL_JSON)
        signals = data.get("signals", [])
        detected = _detect_industry(question)

        scored = [(s, _score_question(question, s, detected)) for s in signals]
        scored.sort(key=lambda x: -x[1])
        top = [s for s, sc in scored if sc > 0][:limit]

        if not top:
            # 兜底：返回检测行业全部信号
            if detected:
                top = [s for s in signals if s.get("industry") == detected][:limit]
            else:
                top = signals[:limit]

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "question": question,
                            "detected_industry": detected,
                            "total_matched": len(top),
                            "signals": top,
                            "note": "返回的是判断层（信号+信息差依据），不是原始数据——这是与 akshare/新浪等数据源的本质区别"
                        },
                        ensure_ascii=False,
                        indent=2
                    )
                }
            ]
        }
    except Exception as e:
        return {"error": {"code": -32000, "message": str(e)}}


def handle_list_articles(args: dict) -> dict:
    """列出研究文章清单（标题/主题/链接）"""
    try:
        if not ARTICLES_DIR.exists():
            return {"error": {"code": -32004, "message": "articles 目录不存在"}}

        topic = args.get("topic", "")
        limit = int(args.get("limit", 20))

        articles = []
        for f in sorted(ARTICLES_DIR.glob("*.md")):
            title = f.stem
            if topic and topic not in title:
                continue
            # 读取首行作为标题
            try:
                first_line = f.read_text(encoding="utf-8").split("\n")[0].replace("#", "").strip()[:80]
            except Exception:
                first_line = title
            articles.append({
                "file": title + ".md",
                "title": first_line,
                "url": f"https://lory69060.github.io/cn-intel-board/articles/{title}.md"
            })

        articles = articles[:limit]
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {"total": len(articles), "articles": articles},
                        ensure_ascii=False,
                        indent=2
                    )
                }
            ]
        }
    except Exception as e:
        return {"error": {"code": -32000, "message": str(e)}}


def handle_read_article(args: dict) -> dict:
    """读取指定文章全文"""
    try:
        if not ARTICLES_DIR.exists():
            return {"error": {"code": -32004, "message": "articles 目录不存在"}}

        title = args.get("title", "")
        if not title:
            return {"error": {"code": -32002, "message": "title 必填"}}

        # 模糊匹配：标题或文件名包含
        match = None
        for f in ARTICLES_DIR.glob("*.md"):
            if title in f.stem or title in f.name:
                match = f
                break
        if not match:
            return {"error": {"code": -32005, "message": f"未找到文章: {title}（可用 list_articles 查看清单）"}}

        content = match.read_text(encoding="utf-8")
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {"file": match.name, "content": content[:8000], "truncated": len(content) > 8000},
                        ensure_ascii=False,
                        indent=2
                    )
                }
            ]
        }
    except Exception as e:
        return {"error": {"code": -32000, "message": str(e)}}


def handle_tools_call(name: str, args: dict) -> dict:
    if name == "read_signal_board":
        try:
            with open(SIGNAL_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)

            signals = data.get("signals", [])
            industry = args.get("industry")
            limit = args.get("limit")
            result_filter = args.get("result")

            if industry:
                signals = [s for s in signals if industry in s.get("industry", "")]
            if result_filter:
                signals = [s for s in signals if s.get("result") == result_filter]
            if limit:
                signals = signals[:int(limit)]

            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"total": len(signals), "signals": signals, "source": str(SIGNAL_JSON)},
                            ensure_ascii=False,
                            indent=2
                        )
                    }
                ]
            }
        except Exception as e:
            return {"error": {"code": -32000, "message": str(e)}}
    elif name == "read_earnings_tracker":
        return handle_earnings_tracker(args)
    elif name == "get_track_record":
        return handle_track_record(args)
    elif name == "ask_edge":
        return handle_ask_edge(args)
    elif name == "list_articles":
        return handle_list_articles(args)
    elif name == "read_article":
        return handle_read_article(args)
    else:
        return {"error": {"code": -32601, "message": f"Unknown tool: {name}"}}


def main_loop() -> None:
    """JSON-RPC 2.0 over stdio 主循环"""
    while True:
        try:
            raw = sys.stdin.readline()
            if not raw:
                break
            raw = raw.strip()
            if not raw:
                continue

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                _send({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None})
                continue

            method = msg.get("method", "")
            msg_id = msg.get("id")
            params = msg.get("params", {})

            if method == "tools/list":
                result = handle_tools_list()
                _send({"jsonrpc": "2.0", "result": result, "id": msg_id})
            elif method == "tools/call":
                tool_name = params.get("name", "")
                tool_args = params.get("arguments", {})
                result = handle_tools_call(tool_name, tool_args)
                _send({"jsonrpc": "2.0", "result": result, "id": msg_id})
            elif method == "initialize":
                _send({
                    "jsonrpc": "2.0",
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "mcp-intel-server", "version": "0.1.0"}
                    },
                    "id": msg_id
                })
            elif method == "notifications/initialized":
                pass  # 无需响应
            else:
                _send({"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Method not found: {method}"}, "id": msg_id})

        except Exception as e:
            traceback.print_exc()
            _send({"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}, "id": None})


if __name__ == "__main__":
    main_loop()

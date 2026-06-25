#!/usr/bin/env python3
"""
把采集器输出的 JSON 数据发给本地 Hermes 模型分析。

支持的后端（OpenAI 兼容接口）：
  Ollama    http://localhost:11434/v1   模型名: hermes3 / nous-hermes2 ...
  LM Studio http://localhost:1234/v1   模型名: 与 LM Studio 加载的一致

用法示例：
  python hermes_chat.py output/research_data_*.json
  python hermes_chat.py output/research_data_*.json --ask "哪篇论文最值得精读？"
  python hermes_chat.py output/research_data_*.json --backend lmstudio --model hermes-3-8b
  python hermes_chat.py output/research_data_*.json --max-records 20 --no-stream
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
import os

# ── 预设后端 ────────────────────────────────────────────────────────────────
BACKENDS = {
    "ollama":   {"base_url": "http://localhost:11434/v1", "default_model": "hermes3"},
    "lmstudio": {"base_url": "http://localhost:1234/v1",  "default_model": "hermes-3-8b-instruct"},
    "openai":   {"base_url": "https://api.openai.com/v1", "default_model": "gpt-4o-mini"},
}

DEFAULT_QUESTION = (
    "请根据以上研究数据，给我一份简洁的中文分析报告，包含：\n"
    "1. 数据整体概览（来源、数量、类型）\n"
    "2. 最重要的 3-5 条研究发现或趋势\n"
    "3. 你认为最值得深入研究的方向\n"
    "4. 如有论文/仓库，列出 TOP 3 推荐"
)


def load_records(path: str, max_records: int) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    records = data if isinstance(data, list) else data.get("records", [])
    return records[:max_records]


def format_record(r: dict) -> str:
    """把一条采集记录压缩成简短文本，避免撑爆上下文。"""
    rtype = r.get("type", r.get("source", "unknown"))
    lines = [f"[{rtype}]"]

    for key in ("title", "full_name", "name"):
        if r.get(key):
            lines.append(f"标题: {r[key]}")
            break

    for key in ("abstract", "description", "body", "snippet"):
        val = r.get(key, "")
        if val:
            lines.append(f"摘要: {str(val)[:300]}")
            break

    for key in ("authors", "author"):
        val = r.get(key)
        if val:
            lines.append(f"作者: {val if isinstance(val, str) else ', '.join(val[:3])}")
            break

    for key in ("published", "date", "created_at", "updated_at"):
        if r.get(key):
            lines.append(f"日期: {r[key][:10]}")
            break

    for key in ("url", "doi", "link"):
        if r.get(key):
            lines.append(f"链接: {r[key]}")
            break

    for key in ("stars", "citations"):
        if r.get(key) is not None:
            lines.append(f"热度: {r[key]}")
            break

    return "\n".join(lines)


def build_prompt(records: list[dict], question: str) -> str:
    formatted = "\n\n".join(f"--- 记录 {i+1} ---\n{format_record(r)}" for i, r in enumerate(records))
    return (
        f"以下是从研究数据采集系统获取的 {len(records)} 条数据：\n\n"
        f"{formatted}\n\n"
        f"---\n\n{question}"
    )


def chat(base_url: str, model: str, prompt: str, stream: bool, api_key: str) -> None:
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一名专业的研究助手，善于分析学术文献和技术数据。请用中文回答。"},
            {"role": "user",   "content": prompt},
        ],
        "stream": stream,
        "temperature": 0.3,
    }).encode()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key or 'ollama'}",  # Ollama 不验证 key，随意填
    }

    url = f"{base_url.rstrip('/')}/chat/completions"
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            if stream:
                _print_stream(resp)
            else:
                body = json.loads(resp.read())
                print(body["choices"][0]["message"]["content"])
    except urllib.error.URLError as e:
        print(f"\n[错误] 无法连接到 {url}\n原因: {e.reason}", file=sys.stderr)
        print("请确认 Ollama / LM Studio 已启动，且模型已加载。", file=sys.stderr)
        sys.exit(1)


def _print_stream(resp) -> None:
    for raw_line in resp:
        line = raw_line.decode("utf-8").strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            break
        try:
            chunk = json.loads(payload)
            delta = chunk["choices"][0].get("delta", {})
            token = delta.get("content", "")
            if token:
                print(token, end="", flush=True)
        except (json.JSONDecodeError, KeyError, IndexError):
            continue
    print()  # 最后换行


def main():
    parser = argparse.ArgumentParser(description="把采集数据发给 Hermes 分析")
    parser.add_argument("input", help="采集器输出的 JSON 文件路径")
    parser.add_argument("--ask", default=DEFAULT_QUESTION, help="向 Hermes 提的问题")
    parser.add_argument("--backend", choices=list(BACKENDS.keys()), default="ollama",
                        help="LLM 后端 (默认: ollama)")
    parser.add_argument("--base-url", help="自定义 API base URL（覆盖 --backend）")
    parser.add_argument("--model", help="模型名称（覆盖后端默认值）")
    parser.add_argument("--max-records", type=int, default=30,
                        help="最多发送的记录条数（默认 30，避免超出上下文）")
    parser.add_argument("--no-stream", action="store_true", help="关闭流式输出，等待完整回复")
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""),
                        help="API Key（Ollama/LM Studio 不需要）")
    args = parser.parse_args()

    backend = BACKENDS[args.backend]
    base_url = args.base_url or backend["base_url"]
    model    = args.model    or backend["default_model"]

    records = load_records(args.input, args.max_records)
    if not records:
        print("数据文件为空，请先运行 python main.py 采集数据。")
        sys.exit(1)

    print(f"已加载 {len(records)} 条记录，正在发送给 {model} ({base_url}) …\n")
    print("=" * 60)

    prompt = build_prompt(records, args.ask)
    chat(base_url, model, prompt, stream=not args.no_stream, api_key=args.api_key)


if __name__ == "__main__":
    main()

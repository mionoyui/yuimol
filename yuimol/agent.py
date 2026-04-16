"""
Claude エージェントループ
"""

import json

from .constants import SYSTEM_PROMPT
from .tools import TOOL_DEFINITIONS, TOOL_DISPATCH


DEFAULT_MODEL = "claude-sonnet-4-6"


def run_agent_loop(
    user_message: str,
    history: list[dict],
    cmd,
    tool_callback=None,
    tool_executor=None,
    model: str = DEFAULT_MODEL,
) -> tuple[str, list[dict]]:
    """
    1ターン分のエージェントループ。

    Parameters
    ----------
    user_message : str
    history : list[dict]
    cmd : PyMOL cmd オブジェクト
    tool_callback : callable(name, summary) | None
        ツール呼び出し前に呼ばれる通知コールバック（UIのログ表示用）。
    tool_executor : callable(name, input_dict) -> dict | None
        ツールを実際に実行する関数。
        None の場合は TOOL_DISPATCH から直接実行（ヘッドレス・テスト用）。
        GUI モードでは QThread → メインスレッドへの dispatch を渡す。
    """
    import anthropic

    client = anthropic.Anthropic()

    history = list(history)
    history.append({"role": "user", "content": user_message})

    # system と tools はターン間で変わらないのでキャッシュする
    system_with_cache = [
        {"type": "text", "text": SYSTEM_PROMPT,
         "cache_control": {"type": "ephemeral"}}
    ]
    tools_with_cache = [
        {**t, "cache_control": {"type": "ephemeral"}}
        if i == len(TOOL_DEFINITIONS) - 1 else t
        for i, t in enumerate(TOOL_DEFINITIONS)
    ]

    while True:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_with_cache,
            tools=tools_with_cache,
            messages=history,
        )

        content_serializable = []
        for block in response.content:
            if block.type == "text":
                content_serializable.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                content_serializable.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        history.append({"role": "assistant", "content": content_serializable})

        if response.stop_reason == "end_turn":
            text = "\n".join(
                b.text for b in response.content
                if hasattr(b, "text") and b.type == "text"
            )
            return text, history

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                if tool_callback:
                    tool_callback(block.name, json.dumps(block.input, ensure_ascii=False)[:120])

                if tool_executor is not None:
                    # GUI モード: メインスレッドへ dispatch
                    try:
                        result = tool_executor(block.name, block.input)
                    except Exception as e:
                        result = {"error": str(e)}
                else:
                    # ヘッドレス・テストモード: 直接実行
                    fn = TOOL_DISPATCH.get(block.name)
                    if fn is None:
                        result = {"error": f"Unknown tool: {block.name}"}
                    else:
                        try:
                            result = fn(cmd, block.input)
                        except Exception as e:
                            result = {"error": str(e)}

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

            history.append({"role": "user", "content": tool_results})

        else:
            return f"[Unexpected stop reason: {response.stop_reason}]", history

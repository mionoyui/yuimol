"""
yuimol MCP サーバー

XML-RPC サーバー（pymol -R で起動）に接続し、
Claude Code からコマンドを直接実行できるようにする。

使い方:
    1. XML-RPC モードで起動: pixi run yuimol
    2. MCP サーバーを起動: yuimol-mcp (Claude Code が自動起動)
"""

import xmlrpc.client
from fastmcp import FastMCP

PYMOL_XMLRPC_URL = "http://localhost:9123/RPC2"

mcp = FastMCP("yuimol")


@mcp.tool()
def run_pymol_command(command: str) -> str:
    """
    PyMOL コマンドを実行する。

    Parameters
    ----------
    command : str
        PyMOL コマンド文字列。例: "fetch 1CA2", "color magenta, resi 64"
    """
    try:
        proxy = xmlrpc.client.ServerProxy(PYMOL_XMLRPC_URL)
        proxy.do(command)
        return f"OK: {command}"
    except ConnectionRefusedError:
        return "Error: yuimolが起動していないか XML-RPC が有効になっていません。`pixi run yuimol` で起動してください。"
    except Exception as e:
        return f"Error: {e}"


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

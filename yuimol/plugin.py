"""
PyMOL プラグイン エントリポイント
"""

import os

from .gui import ChatPanel

# パネル参照をモジュールレベルで保持（外部からアクセス可能）
_panel_ref = [None]


def _load_dotenv():
    """プラグインディレクトリ or ~/.pymol/startup/yuimol/.env を読む。"""
    candidates = [
        os.path.join(os.path.dirname(__file__), ".env"),
        os.path.expanduser("~/.pymol/startup/yuimol/.env"),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        os.environ.setdefault(k.strip(), v.strip())
            break


def send_chat_message(text: str):
    """チャットパネルにメッセージをプログラムから送信する。"""
    panel = _panel_ref[0]
    if panel is None:
        print("[yuimol] Chat panel not open.")
        return
    panel._input.setText(text)
    panel._send()


def __init_plugin__(app=None):
    """PyMOL プラグインエントリポイント。"""
    from pymol.plugins import addmenuitemqt
    from pymol.gui import get_qtwindow
    from pymol import cmd

    _load_dotenv()

    # fetch したPDBファイルをプロジェクトルートに散らかさないよう
    # ~/.pymol/fetch/ に集約する
    fetch_cache = os.path.expanduser("~/.pymol/fetch")
    os.makedirs(fetch_cache, exist_ok=True)
    cmd.set("fetch_path", fetch_cache)

    def open_panel():
        window = get_qtwindow()
        if window is None:
            print("[yuimol] Qt GUI not available.")
            return

        if _panel_ref[0] is None:
            from pymol.Qt import QtCore
            panel = ChatPanel.create(cmd)
            window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, panel)
            _panel_ref[0] = panel

        _panel_ref[0].show()
        _panel_ref[0].raise_()

    addmenuitemqt("LLM Assistant", open_panel)
    print("[yuimol] Plugin loaded. Use Plugin > LLM Assistant to open the chat panel.")
    open_panel()

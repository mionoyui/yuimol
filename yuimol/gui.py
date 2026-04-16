"""
Qt GUI コンポーネント
- SettingsDialog: APIキー設定ダイアログ
- ChatWorker    : QThread でエージェントループを実行
- ChatPanel     : QDockWidget のチャットパネル

クラッシュ対策:
  PyMOL の cmd.* 操作はメインスレッドでしか安全に呼べない。
  ChatWorker はツール実行が必要になると tool_request シグナルを emit してブロックし、
  メインスレッド（ChatPanel）がツールを実行して結果を返す。
"""

import json
import os

from .agent import run_agent_loop, DEFAULT_MODEL
from .commands import is_pymol_command
from .tools import TOOL_DISPATCH, tool_run_pymol_command, tool_render_nice


_ENV_PATH = os.path.expanduser("~/.pymol/startup/yuimol/.env")


def _get_qt():
    from pymol.Qt import QtCore, QtWidgets
    return QtCore, QtWidgets


def _save_api_key(key: str):
    """APIキーを .env ファイルに保存し、即時 environ にも反映する。"""
    os.makedirs(os.path.dirname(_ENV_PATH), exist_ok=True)

    # 既存の行を読み込み ANTHROPIC_API_KEY だけ上書き
    lines = []
    if os.path.exists(_ENV_PATH):
        with open(_ENV_PATH) as f:
            lines = [l for l in f.readlines() if not l.startswith("ANTHROPIC_API_KEY")]
    lines.append(f"ANTHROPIC_API_KEY={key}\n")

    with open(_ENV_PATH, "w") as f:
        f.writelines(lines)

    os.environ["ANTHROPIC_API_KEY"] = key


AVAILABLE_MODELS = [
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
    "claude-opus-4-6",
]


def _save_model(model: str):
    os.makedirs(os.path.dirname(_ENV_PATH), exist_ok=True)
    lines = []
    if os.path.exists(_ENV_PATH):
        with open(_ENV_PATH) as f:
            lines = [l for l in f.readlines() if not l.startswith("YUIMOL_MODEL")]
    lines.append(f"YUIMOL_MODEL={model}\n")
    with open(_ENV_PATH, "w") as f:
        f.writelines(lines)
    os.environ["YUIMOL_MODEL"] = model


def _load_model() -> str:
    return os.environ.get("YUIMOL_MODEL", DEFAULT_MODEL)


class SettingsDialog:
    """
    APIキー設定ダイアログ。
    Qt が使えない環境ではインポートエラーを避けるため遅延定義。
    """
    _class = None

    @classmethod
    def open(cls, parent=None):
        if cls._class is None:
            _, QtWidgets = _get_qt()

            class _Dialog(QtWidgets.QDialog):
                def __init__(self, parent=None):
                    super().__init__(parent)
                    self.setWindowTitle("LLM Assistant — Settings")
                    self.setMinimumWidth(420)
                    self._build_ui()

                def _build_ui(self):
                    layout = QtWidgets.QVBoxLayout(self)
                    layout.setSpacing(10)
                    layout.setContentsMargins(16, 16, 16, 16)

                    # 説明文
                    desc = QtWidgets.QLabel(
                        "Anthropic API キーを入力してください。\n"
                        "キーは <b>~/.pymol/startup/yuimol/.env</b> に保存されます。"
                    )
                    desc.setWordWrap(True)
                    layout.addWidget(desc)

                    # APIキー入力
                    self._key_input = QtWidgets.QLineEdit()
                    self._key_input.setPlaceholderText("sk-ant-...")
                    self._key_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
                    current = os.environ.get("ANTHROPIC_API_KEY", "")
                    if current:
                        self._key_input.setText(current)
                    layout.addWidget(self._key_input)

                    # 表示/非表示トグル
                    self._show_cb = QtWidgets.QCheckBox("APIキーを表示する")
                    self._show_cb.stateChanged.connect(self._toggle_visibility)
                    layout.addWidget(self._show_cb)

                    # モデル選択
                    layout.addWidget(QtWidgets.QLabel("モデル:"))
                    self._model_combo = QtWidgets.QComboBox()
                    for m in AVAILABLE_MODELS:
                        self._model_combo.addItem(m)
                    current_model = _load_model()
                    if current_model in AVAILABLE_MODELS:
                        self._model_combo.setCurrentIndex(AVAILABLE_MODELS.index(current_model))
                    layout.addWidget(self._model_combo)

                    # ボタン
                    btn_row = QtWidgets.QHBoxLayout()
                    btn_row.addStretch()
                    cancel_btn = QtWidgets.QPushButton("キャンセル")
                    cancel_btn.clicked.connect(self.reject)
                    save_btn = QtWidgets.QPushButton("保存")
                    save_btn.setDefault(True)
                    save_btn.clicked.connect(self._save)
                    btn_row.addWidget(cancel_btn)
                    btn_row.addWidget(save_btn)
                    layout.addLayout(btn_row)

                def _toggle_visibility(self, state):
                    _, QtWidgets = _get_qt()
                    if state:
                        self._key_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Normal)
                    else:
                        self._key_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)

                def _save(self):
                    key = self._key_input.text().strip()
                    if not key:
                        _, QtWidgets = _get_qt()
                        QtWidgets.QMessageBox.warning(self, "入力エラー", "APIキーを入力してください。")
                        return
                    _save_api_key(key)
                    _save_model(self._model_combo.currentText())
                    self.accept()

            cls._class = _Dialog

        dialog = cls._class(parent)
        return dialog.exec()


class ChatWorker:
    """
    QThread サブクラス。run_agent_loop を別スレッドで実行する。
    Qt が使えない環境ではインポートエラーを避けるため遅延定義。
    """
    _class = None

    @classmethod
    def create(cls, user_message, history, cmd, model=None):
        if cls._class is None:
            QtCore, _ = _get_qt()

            class _Worker(QtCore.QThread):
                agent_replied   = QtCore.Signal(str)
                tool_called     = QtCore.Signal(str, str)   # name, summary
                tool_request    = QtCore.Signal(str, str, str)  # tool_use_id, name, json_input
                error_occurred  = QtCore.Signal(str)
                history_updated = QtCore.Signal(list)

                def __init__(self, user_message, history, cmd, model):
                    super().__init__()
                    self._user_message = user_message
                    self._history = history
                    self._cmd = cmd
                    self._model = model
                    self._mutex = QtCore.QMutex()
                    self._condition = QtCore.QWaitCondition()
                    self._tool_result: dict | None = None

                def _execute_tool_via_main_thread(self, name: str, inp: dict) -> dict:
                    """
                    ツール実行リクエストをメインスレッドに委譲し、結果が返るまで待機する。
                    """
                    json_input = json.dumps(inp, ensure_ascii=False)
                    self._mutex.lock()
                    self._tool_result = None
                    self.tool_request.emit("", name, json_input)
                    self._condition.wait(self._mutex)
                    result = self._tool_result
                    self._mutex.unlock()
                    return result if result is not None else {"error": "No result from main thread"}

                def receive_tool_result(self, result: dict):
                    """メインスレッドから呼ばれ、ツール結果をワーカーに届ける。"""
                    self._mutex.lock()
                    self._tool_result = result
                    self._condition.wakeAll()
                    self._mutex.unlock()

                def run(self):
                    try:
                        text, new_history = run_agent_loop(
                            self._user_message,
                            self._history,
                            self._cmd,
                            tool_callback=lambda name, summary: self.tool_called.emit(name, summary),
                            tool_executor=self._execute_tool_via_main_thread,
                            model=self._model,
                        )
                        self.history_updated.emit(new_history)
                        self.agent_replied.emit(text)
                    except Exception as e:
                        self.error_occurred.emit(str(e))

            cls._class = _Worker

        return cls._class(user_message, history, cmd, model or _load_model())


class ChatPanel:
    """
    QDockWidget ベースのチャットパネル。
    Qt が使えない環境ではインポートエラーを避けるため遅延定義。
    """
    _class = None

    @classmethod
    def create(cls, cmd):
        if cls._class is None:
            QtCore, QtWidgets = _get_qt()

            class _Panel(QtWidgets.QDockWidget):
                def __init__(self, cmd):
                    super().__init__("LLM Assistant")
                    self._cmd = cmd
                    self._history: list[dict] = []
                    self._worker = None
                    self._build_ui()

                    # APIキー未設定なら起動時にダイアログを表示
                    if not os.environ.get("ANTHROPIC_API_KEY"):
                        QtCore.QTimer.singleShot(300, self._open_settings)

                def _build_ui(self):
                    container = QtWidgets.QWidget()
                    layout = QtWidgets.QVBoxLayout(container)
                    layout.setContentsMargins(4, 4, 4, 4)
                    layout.setSpacing(4)

                    self._display = QtWidgets.QTextBrowser()
                    self._display.setReadOnly(True)
                    self._display.setOpenExternalLinks(False)
                    self._display.setMinimumHeight(200)
                    layout.addWidget(self._display)

                    input_row = QtWidgets.QHBoxLayout()
                    self._input = QtWidgets.QLineEdit()
                    self._input.setPlaceholderText("Ask about the loaded structure... / 構造について質問...")
                    self._input.setMinimumWidth(380)
                    self._input.returnPressed.connect(self._send)
                    self._send_btn = QtWidgets.QPushButton("Send")
                    self._send_btn.setMinimumWidth(60)
                    self._send_btn.clicked.connect(self._send)
                    self._clear_btn = QtWidgets.QPushButton("Clear")
                    self._clear_btn.setMinimumWidth(60)
                    self._clear_btn.clicked.connect(self._clear)
                    self._render_btn = QtWidgets.QPushButton("kawaii")
                    self._render_btn.setMinimumWidth(70)
                    self._render_btn.setToolTip("高品質レンダリング (ray trace)")
                    self._render_btn.clicked.connect(self._render)
                    self._settings_btn = QtWidgets.QPushButton("Settings")
                    self._settings_btn.setMinimumWidth(70)
                    self._settings_btn.setToolTip("API キーの設定")
                    self._settings_btn.clicked.connect(self._open_settings)
                    input_row.addWidget(self._input)
                    input_row.addWidget(self._send_btn)
                    input_row.addWidget(self._clear_btn)
                    input_row.addWidget(self._render_btn)
                    input_row.addWidget(self._settings_btn)
                    layout.addLayout(input_row)

                    self.setWidget(container)
                    self.setMinimumWidth(300)

                def _open_settings(self):
                    SettingsDialog.open(parent=self)

                def _render(self):
                    self._render_btn.setEnabled(False)
                    self._append("tool", "[kawaii render]")
                    try:
                        c = self._cmd
                        c.do("bg_color white")
                        c.set("opaque_background",   1)
                        c.set("depth_cue",           0)
                        c.set("ray_trace_mode",      1)
                        c.set("ray_trace_color",     "0x404040")
                        c.set("antialias",           4)
                        c.set("ambient",             0.85)
                        c.set("cartoon_oval_width",  0.3)
                        c.set("cartoon_oval_length", 1.3)
                        c.set("ray_trace_gain",      0.03)
                        c.set("specular",            0.02)
                        c.set("light_count",         6)
                        c.set("reflect",             0.05)
                        w, h = c.get_viewport()
                        c.ray(w, h)
                        self._append("assistant", "kawaii ✨")
                    except Exception as e:
                        self._append("error", str(e))
                    finally:
                        self._render_btn.setEnabled(True)

                def _send(self):
                    text = self._input.text().strip()
                    if not text:
                        return
                    if self._worker is not None and self._worker.isRunning():
                        return

                    self._input.clear()
                    self._append("user", text)

                    # PyMOL コマンドと判定できる場合はメインスレッドで直接実行
                    if is_pymol_command(text):
                        result = tool_run_pymol_command(self._cmd, {"command": text})
                        if "error" in result:
                            self._append("error", result["error"])
                        else:
                            parts = []
                            if "rmsd" in result:
                                parts.append(f"RMSD: {result['rmsd']} Å  ({result.get('atoms', '?')} atoms)")
                            parts.append(f"objects: {result.get('objects', [])}")
                            self._append("tool", f"[direct] {text}  →  {', '.join(parts)}")
                        self._send_btn.setEnabled(True)
                        return

                    self._send_btn.setEnabled(False)
                    self._worker = ChatWorker.create(text, self._history, self._cmd)
                    self._worker.agent_replied.connect(self._on_reply)
                    self._worker.tool_called.connect(self._on_tool)
                    self._worker.tool_request.connect(self._on_tool_request)
                    self._worker.error_occurred.connect(self._on_error)
                    self._worker.history_updated.connect(self._on_history)
                    self._worker.start()

                def _on_tool_request(self, _tool_use_id: str, name: str, json_input: str):
                    """メインスレッドでツールを実行し、結果をワーカーに返す。"""
                    try:
                        inp = json.loads(json_input)
                        fn = TOOL_DISPATCH.get(name)
                        if fn is None:
                            result = {"error": f"Unknown tool: {name}"}
                        else:
                            result = fn(self._cmd, inp)
                    except Exception as e:
                        result = {"error": str(e)}
                    self._worker.receive_tool_result(result)

                def _on_reply(self, text: str):
                    self._append("assistant", text)
                    self._send_btn.setEnabled(True)

                def _on_tool(self, name: str, summary: str):
                    self._append("tool", f"[{name}] {summary}")

                def _on_error(self, msg: str):
                    self._append("error", msg)
                    self._send_btn.setEnabled(True)

                def _on_history(self, history: list):
                    self._history = history

                def _clear(self):
                    self._history = []
                    self._display.clear()

                def _append(self, role: str, text: str):
                    safe_text = (
                        text
                        .replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                        .replace("\n", "<br>")
                    )

                    if role == "user":
                        html = (
                            '<table width="100%" cellpadding="0" cellspacing="2">'
                            '<tr><td width="20%"></td>'
                            '<td style="background:#2980b9;color:white;padding:8px 10px;">'
                            f'<b>You</b><br>{safe_text}</td></tr></table>'
                        )
                    elif role == "assistant":
                        html = (
                            '<table width="100%" cellpadding="0" cellspacing="2">'
                            '<tr><td style="background:#ecf0f1;color:#2c3e50;padding:8px 10px;">'
                            f'<b>Assistant</b><br>{safe_text}</td>'
                            '<td width="20%"></td></tr></table>'
                        )
                    elif role == "tool":
                        html = (
                            '<table width="100%" cellpadding="0" cellspacing="0">'
                            '<tr><td style="border-top:1px solid #bdc3c7;padding:2px 6px;'
                            'color:#7f8c8d;font-size:10px;font-family:monospace;">'
                            f'&#9881; {safe_text}</td></tr></table>'
                        )
                    elif role == "error":
                        html = (
                            '<table width="100%" cellpadding="0" cellspacing="2">'
                            '<tr><td style="background:#fadbd8;color:#c0392b;padding:8px 10px;">'
                            f'<b>Error</b><br>{safe_text}</td></tr></table>'
                        )
                    else:
                        html = f'<div style="padding:4px;">{safe_text}</div>'

                    self._display.insertHtml(html)
                    self._display.insertHtml("<br>")
                    sb = self._display.verticalScrollBar()
                    sb.setValue(sb.maximum())

            cls._class = _Panel

        return cls._class(cmd)

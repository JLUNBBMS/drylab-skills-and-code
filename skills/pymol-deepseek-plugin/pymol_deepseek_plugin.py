"""
DeepSeek AI assistant for PyMOL.

Version 3.1.0
- Dockable, resizable assistant panel integrated into the PyMOL main window
- Rich chat transcript and separate tool log
- Multi-line prompt editor, model settings, session rollback, and safer Python mode
- Editable maximum tool-call turns directly in the chat window (0 = unlimited)

PyMOL commands:
    deepseek_chat
    deepseek <request>
    deepseek_stop
    deepseek_reset
    deepseek_undo
    deepseek_model [model]
    deepseek_turns [number]
    deepseek_status
"""

from pymol import cmd
import copy
import html
import io
import json
import math
import os
import re
import subprocess
import sys
import threading
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_PLUGIN_VERSION = "3.1.0"
_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".pymol")
_KEY_FILE = os.path.join(_CONFIG_DIR, "deepseek_key")
_CONFIG_FILE = os.path.join(_CONFIG_DIR, "deepseek_config.json")
_DEFAULT_BASE_URL = "https://api.deepseek.com"
_DEFAULT_MODEL = "deepseek-v4-flash"
_DEFAULT_THINKING = "disabled"
_DEFAULT_MAX_TOOL_TURNS = 12


def _read_config() -> dict:
    try:
        with open(_CONFIG_FILE, encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _write_config(updates: dict) -> None:
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    config = _read_config()
    config.update(updates)
    with open(_CONFIG_FILE, "w", encoding="utf-8") as handle:
        json.dump(config, handle, ensure_ascii=False, indent=2)
    try:
        os.chmod(_CONFIG_FILE, 0o600)
    except OSError:
        pass


def _get_base_url() -> str:
    value = os.environ.get("DEEPSEEK_BASE_URL", "").strip()
    if not value:
        value = str(_read_config().get("base_url", _DEFAULT_BASE_URL)).strip()
    return (value or _DEFAULT_BASE_URL).rstrip("/")


def _get_model() -> str:
    value = os.environ.get("DEEPSEEK_MODEL", "").strip()
    if not value:
        value = str(_read_config().get("model", _DEFAULT_MODEL)).strip()
    return value or _DEFAULT_MODEL


def _get_thinking_mode() -> str:
    value = os.environ.get("DEEPSEEK_THINKING", "").strip().lower()
    if not value:
        value = str(_read_config().get("thinking", _DEFAULT_THINKING)).strip().lower()
    return value if value in {"enabled", "disabled"} else _DEFAULT_THINKING


def _get_max_tool_turns() -> int:
    """Return the per-request agent tool-call turn limit; 0 means unlimited."""
    raw = os.environ.get("DEEPSEEK_MAX_TOOL_TURNS", "").strip()
    if not raw:
        raw = str(_read_config().get("max_tool_turns", _DEFAULT_MAX_TOOL_TURNS)).strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = _DEFAULT_MAX_TOOL_TURNS
    return max(0, min(value, 1000))


def _set_max_tool_turns(value: int) -> int:
    """Persist and apply the tool-call turn limit for this PyMOL process."""
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = _DEFAULT_MAX_TOOL_TURNS
    normalized = max(0, min(normalized, 1000))
    os.environ["DEEPSEEK_MAX_TOOL_TURNS"] = str(normalized)
    _write_config({"max_tool_turns": normalized})
    return normalized


def _load_api_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    if os.path.exists(_KEY_FILE):
        try:
            with open(_KEY_FILE, encoding="utf-8") as handle:
                return handle.read().strip()
        except Exception:
            pass
    return ""


def _save_api_key(key: str) -> None:
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    with open(_KEY_FILE, "w", encoding="utf-8") as handle:
        handle.write(key.strip())
    try:
        os.chmod(_KEY_FILE, 0o600)
    except OSError:
        pass


def _unsafe_enabled() -> bool:
    return os.environ.get("PYMOL_DEEPSEEK_ALLOW_UNSAFE", "").strip() == "1"


def _set_unsafe_enabled(enabled: bool) -> None:
    if enabled:
        os.environ["PYMOL_DEEPSEEK_ALLOW_UNSAFE"] = "1"
    else:
        os.environ.pop("PYMOL_DEEPSEEK_ALLOW_UNSAFE", None)


# ---------------------------------------------------------------------------
# Dependency setup
# ---------------------------------------------------------------------------


def _ensure_openai() -> None:
    try:
        import openai  # noqa: F401
        return
    except ImportError:
        pass

    print("DeepSeek plugin: 'openai' not found — installing now (one-time setup)…")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", "openai"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("DeepSeek plugin: 'openai' installed successfully. Restart PyMOL if needed.")
    else:
        print(f"DeepSeek plugin: pip install failed:\n{result.stderr}")


threading.Thread(target=_ensure_openai, daemon=True).start()


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

_history: list = []
_stop_event = threading.Event()
_is_running = False
_chat_panel = None
_chat_container = None
_last_session_snapshot = None
_last_history_checkpoint = 0
_snapshot_lock = threading.Lock()


def _get_openai():
    try:
        import openai
        return openai
    except ImportError:
        print(
            "DeepSeek plugin error: 'openai' package is not installed.\n"
            "Run install_deepseek_deps in the PyMOL command line, then restart PyMOL."
        )
        return None


# ---------------------------------------------------------------------------
# Structured output events
# ---------------------------------------------------------------------------


def _console_line(kind: str, text: str) -> str:
    if kind == "command":
        return f"  PyMOL> {text}"
    if kind == "error":
        return f"DeepSeek error: {text}"
    if kind == "result":
        return f"  {text}"
    return f"DeepSeek: {text}"


def _emit(out_fn, kind: str, text: str) -> None:
    """Emit a structured event, with compatibility for ordinary one-arg callbacks."""
    if out_fn is None:
        print(_console_line(kind, text))
        return
    try:
        out_fn(kind, text)
    except TypeError:
        out_fn(_console_line(kind, text))


# ---------------------------------------------------------------------------
# PyMOL context and rollback snapshot
# ---------------------------------------------------------------------------


def _get_session_context() -> str:
    lines = []
    try:
        objects = cmd.get_names("objects")
    except Exception:
        objects = []

    if objects:
        lines.append(f"Loaded objects ({len(objects)}): {', '.join(objects)}")
        for obj in objects[:12]:
            try:
                chains = cmd.get_chains(obj)
                n_atoms = cmd.count_atoms(obj)
                chain_str = ", ".join(chains) if chains else "—"
                lines.append(f"  • {obj}: {n_atoms} atoms, chains: {chain_str}")
            except Exception:
                lines.append(f"  • {obj}: unable to query")
    else:
        lines.append("No objects currently loaded.")

    try:
        selections = [name for name in cmd.get_names("selections") if not name.startswith("_")]
    except Exception:
        selections = []
    if selections:
        lines.append(f"Named selections: {', '.join(selections[:20])}")

    try:
        lines.append(f"Current state: {cmd.get_state()}")
    except Exception:
        pass
    return "\n".join(lines)


def _capture_snapshot(out_fn=None) -> bool:
    """Best-effort full PyMOL session snapshot for the one-click rollback button."""
    global _last_session_snapshot
    if not hasattr(cmd, "get_session"):
        return False
    try:
        _emit(out_fn, "status", "Creating an undo snapshot for this request…")
        snapshot = cmd.get_session()
        # Some PyMOL builds return mutable nested structures. A deepcopy prevents
        # later operations from mutating our rollback point in place.
        try:
            snapshot = copy.deepcopy(snapshot)
        except Exception:
            pass
        with _snapshot_lock:
            _last_session_snapshot = snapshot
        _emit(out_fn, "snapshot", "ready")
        return True
    except Exception as exc:
        _emit(out_fn, "tool", f"Could not create an undo snapshot: {exc}")
        return False


def _restore_snapshot(out_fn=None, done_fn=None) -> None:
    global _last_session_snapshot, _history
    try:
        with _snapshot_lock:
            snapshot = _last_session_snapshot
        if snapshot is None:
            _emit(out_fn, "status", "There are no AI changes to undo.")
            return
        if not hasattr(cmd, "set_session"):
            _emit(out_fn, "error", "This PyMOL build does not provide cmd.set_session, so the snapshot cannot be restored.")
            return

        _emit(out_fn, "status", "Restoring the PyMOL state from before the latest AI changes…")
        cmd.set_session(snapshot)
        _history = _history[:_last_history_checkpoint]
        with _snapshot_lock:
            _last_session_snapshot = None
        _emit(out_fn, "snapshot", "cleared")
        _emit(out_fn, "status", "The latest AI changes have been undone.")
    except Exception as exc:
        _emit(out_fn, "error", f"Undo failed: {exc}")
    finally:
        if done_fn:
            done_fn()


# ---------------------------------------------------------------------------
# Agent prompt and tools
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert assistant embedded inside PyMOL, molecular visualisation software.
The user talks to you in natural language. You may answer questions or operate the
currently running PyMOL session through tools.

Capabilities:
- Execute normal PyMOL commands with execute_pymol_commands.
- Run structural analyses with run_python_analysis. The script can use cmd, stored,
  and math; printed output is returned to you.
- Help with molecular visualisation, structural biology, crystallography, selections,
  measurements, alignments, rendering, and session organisation.

Rules:
- Use only object and selection names present in the supplied session context unless
  you create a new name explicitly.
- Prefer a small, coherent batch of commands over many separate tool calls.
- For calculations or lists that must be returned to the user, use
  run_python_analysis and print the result.
- After tools finish, reply concisely in the same language as the user.
- Never claim a command succeeded unless the tool result indicates success.
- Avoid destructive commands unless the user clearly requested them.
- Do not use shell commands or local file access unless the user explicitly enabled
  unsafe mode and explicitly requested that operation.

Useful PyMOL commands include fetch, load, show, hide, color, spectrum, select,
zoom, orient, center, label, distance, align, super, save, png, bg_color, set, ray,
create, extract, remove, delete, group, enable, disable, and scene.
"""

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_pymol_commands",
            "description": "Execute one or more ordinary PyMOL commands sequentially.",
            "parameters": {
                "type": "object",
                "properties": {
                    "commands": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ordered list of PyMOL commands.",
                    },
                    "explanation": {
                        "type": "string",
                        "description": "A short English description of the operation.",
                    },
                },
                "required": ["commands", "explanation"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_python_analysis",
            "description": (
                "Run Python for PyMOL structural analysis. In safe mode only cmd, stored, "
                "math and selected builtins are available. Print results for the assistant."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python analysis code."},
                    "explanation": {
                        "type": "string",
                        "description": "A short English description of the analysis.",
                    },
                },
                "required": ["code", "explanation"],
                "additionalProperties": False,
            },
        },
    },
]


def _tool_call_to_dict(tool_call) -> dict:
    return {
        "id": tool_call.id,
        "type": "function",
        "function": {
            "name": tool_call.function.name,
            "arguments": tool_call.function.arguments,
        },
    }


def _parse_tool_arguments(raw: str) -> dict:
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON arguments: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("tool arguments must be a JSON object")
    return value


def _unsafe_pymol_command(command: str) -> bool:
    if _unsafe_enabled():
        return False
    text = command.strip().lower()
    blocked_prefixes = (
        "python",
        "run ",
        "run\t",
        "@",
        "system ",
        "system\t",
        "spawn ",
        "spawn\t",
        "exec ",
        "exec\t",
    )
    return text.startswith(blocked_prefixes)


def _execute_pymol_tool(arguments: dict, out_fn) -> str:
    commands = arguments.get("commands", [])
    explanation = str(arguments.get("explanation", "")).strip()
    if explanation:
        _emit(out_fn, "tool", explanation)
    if not isinstance(commands, list) or not all(isinstance(item, str) for item in commands):
        return "Error: commands must be a list of strings"

    results = []
    for pymol_command in commands[:60]:
        if _stop_event.is_set():
            results.append("✗ stopped by user")
            break
        if _unsafe_pymol_command(pymol_command):
            result = (
                f"✗ {pymol_command} → blocked unsafe command "
                "(enable unrestricted Python only if you understand the risk)"
            )
            results.append(result)
            _emit(out_fn, "error", result)
            continue

        _emit(out_fn, "command", pymol_command)
        buffer = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = buffer
            cmd.do(pymol_command)
        except Exception as exc:
            result = f"✗ {pymol_command} → {exc}"
            results.append(result)
            _emit(out_fn, "error", result)
        finally:
            sys.stdout = old_stdout

        captured = buffer.getvalue().strip()
        if results and results[-1].startswith(f"✗ {pymol_command}"):
            continue
        error_words = ("error", "syntaxerror", "unknown command", "unrecognized")
        if any(word in captured.lower() for word in error_words):
            result = f"✗ {pymol_command} → {captured}"
            results.append(result)
            _emit(out_fn, "error", result)
        else:
            result = f"✓ {pymol_command}" + (f" → {captured}" if captured else "")
            results.append(result)
            _emit(out_fn, "result", result)

    return "\n".join(results) or "(no commands executed)"


def _run_python_tool(arguments: dict, out_fn) -> str:
    code = arguments.get("code", "")
    explanation = str(arguments.get("explanation", "")).strip()
    if explanation:
        _emit(out_fn, "tool", explanation)
    if not isinstance(code, str):
        return "Error: code must be a string"

    import pymol

    if _unsafe_enabled():
        globals_dict = {
            "cmd": cmd,
            "stored": pymol.stored,
            "math": math,
            "__builtins__": __builtins__,
        }
    else:
        safe_builtins = {
            "print": print,
            "len": len,
            "range": range,
            "enumerate": enumerate,
            "zip": zip,
            "sorted": sorted,
            "set": set,
            "list": list,
            "tuple": tuple,
            "dict": dict,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "min": min,
            "max": max,
            "sum": sum,
            "abs": abs,
            "round": round,
            "any": any,
            "all": all,
            "isinstance": isinstance,
            "getattr": getattr,
            "hasattr": hasattr,
            "repr": repr,
            "iter": iter,
            "next": next,
            "map": map,
            "filter": filter,
            "reversed": reversed,
            "slice": slice,
            "Exception": Exception,
            "ValueError": ValueError,
            "TypeError": TypeError,
            "KeyError": KeyError,
            "IndexError": IndexError,
        }
        globals_dict = {
            "cmd": cmd,
            "stored": pymol.stored,
            "math": math,
            "__builtins__": safe_builtins,
        }

    buffer = io.StringIO()
    old_stdout = sys.stdout
    try:
        sys.stdout = buffer
        exec(code, globals_dict, {})  # noqa: S102 - intentionally controlled by mode
        output = buffer.getvalue().strip() or "(no output)"
        _emit(out_fn, "result", output)
        return output
    except Exception as exc:
        output = buffer.getvalue().strip()
        message = f"Error: {exc}" + (f"\n{output}" if output else "")
        _emit(out_fn, "error", message)
        return message
    finally:
        sys.stdout = old_stdout


# ---------------------------------------------------------------------------
# DeepSeek agent loop
# ---------------------------------------------------------------------------


def _run_deepseek(query: str, api_key: str, out_fn=None, done_fn=None) -> None:
    global _is_running, _last_history_checkpoint
    _is_running = True
    _stop_event.clear()

    try:
        openai_module = _get_openai()
        if not openai_module:
            _emit(out_fn, "error", "The OpenAI SDK is not installed.")
            return

        _last_history_checkpoint = len(_history)
        _capture_snapshot(out_fn)

        session_context = _get_session_context()
        user_message = (
            f"## Current PyMOL session\n{session_context}\n\n"
            f"## User request\n{query}"
        )
        _history.append({"role": "user", "content": user_message})

        model = _get_model()
        thinking = _get_thinking_mode()
        _emit(out_fn, "status", f"Connecting to {model}…")

        client = openai_module.OpenAI(
            api_key=api_key,
            base_url=_get_base_url(),
            timeout=180.0,
        )

        max_turns = _get_max_tool_turns()
        turns = 0
        completed = False
        limit_text = "Unlimited" if max_turns == 0 else str(max_turns)
        _emit(out_fn, "status", f"Tool-call turn limit: {limit_text}")
        while max_turns == 0 or turns < max_turns:
            if _stop_event.is_set():
                _emit(out_fn, "status", "Stopped.")
                return
            turns += 1

            request = {
                "model": model,
                "max_tokens": 8192,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + _history,
                "tools": _TOOLS,
                "tool_choice": "auto",
                "extra_body": {"thinking": {"type": thinking}},
            }
            try:
                response = client.chat.completions.create(**request)
            except TypeError:
                # Compatibility with old OpenAI SDK versions that do not accept extra_body.
                request.pop("extra_body", None)
                response = client.chat.completions.create(**request)
            except Exception as exc:
                _emit(out_fn, "error", str(exc))
                return

            if not response.choices:
                _emit(out_fn, "error", "The API response did not include any choices.")
                return

            message = response.choices[0].message
            content = message.content or ""
            if content.strip():
                _emit(out_fn, "assistant", content.strip())

            assistant_message = {"role": "assistant", "content": content}
            reasoning_content = getattr(message, "reasoning_content", None)
            if reasoning_content:
                assistant_message["reasoning_content"] = reasoning_content

            tool_calls = list(message.tool_calls or [])
            if tool_calls:
                assistant_message["tool_calls"] = [_tool_call_to_dict(call) for call in tool_calls]
            _history.append(assistant_message)

            if not tool_calls:
                completed = True
                break

            for tool_call in tool_calls:
                if _stop_event.is_set():
                    break
                try:
                    arguments = _parse_tool_arguments(tool_call.function.arguments)
                    if tool_call.function.name == "execute_pymol_commands":
                        result_content = _execute_pymol_tool(arguments, out_fn)
                    elif tool_call.function.name == "run_python_analysis":
                        result_content = _run_python_tool(arguments, out_fn)
                    else:
                        result_content = f"Error: unknown tool {tool_call.function.name}"
                        _emit(out_fn, "error", result_content)
                except Exception as exc:
                    result_content = f"Error: {exc}"
                    _emit(out_fn, "error", result_content)

                _history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_content,
                    }
                )

        if not completed and max_turns > 0 and turns >= max_turns:
            _emit(
                out_fn,
                "error",
                f'The {max_turns}-turn tool-call limit has been reached. Increase \"Turn limit\" at the top of the panel, or set it to 0 for unlimited calls.',
            )
        else:
            _emit(out_fn, "status", "Ready")
    finally:
        _is_running = False
        if done_fn:
            done_fn()


def _prompt_api_key() -> str:
    try:
        from pymol.Qt import QtWidgets

        app = QtWidgets.QApplication.instance()
        parent = app.activeWindow() if app else None
        field = QtWidgets.QLineEdit()
        field.setEchoMode(QtWidgets.QLineEdit.Password)
        dialog = QtWidgets.QDialog(parent)
        dialog.setWindowTitle("DeepSeek API Key")
        layout = QtWidgets.QVBoxLayout(dialog)
        label = QtWidgets.QLabel(
            "Enter your DeepSeek API key. It is stored locally only in ~/.pymol/deepseek_key."
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addWidget(field)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec_() and field.text().strip():
            key = field.text().strip()
            _save_api_key(key)
            return key
    except Exception as exc:
        print(f"DeepSeek: could not open key dialog ({exc})")
    return ""


def _dispatch_deepseek(query: str, out_fn=None, done_fn=None) -> None:
    query = str(query).strip()
    if not query:
        _emit(out_fn, "status", "Enter a natural-language question or PyMOL instruction.")
        if done_fn:
            done_fn()
        return
    if _is_running:
        _emit(out_fn, "status", "A task is already running. Stop it or wait for it to finish.")
        return

    api_key = _load_api_key() or _prompt_api_key()
    if not api_key:
        _emit(out_fn, "error", "No API key was provided.")
        if done_fn:
            done_fn()
        return

    thread = threading.Thread(
        target=_run_deepseek,
        args=(query, api_key),
        kwargs={"out_fn": out_fn, "done_fn": done_fn},
        daemon=True,
    )
    thread.start()


# ---------------------------------------------------------------------------
# Rich docked Qt interface
# ---------------------------------------------------------------------------


def _markdown_to_html(text: str) -> str:
    """Small dependency-free Markdown renderer suitable for model responses."""
    escaped = html.escape(text.strip())
    code_blocks = []

    def stash_code(match):
        language = html.escape(match.group(1) or "")
        code = match.group(2).strip("\n")
        token = f"@@CODEBLOCK{len(code_blocks)}@@"
        code_blocks.append(
            f'<pre class="code"><span class="lang">{language}</span>{code}</pre>'
        )
        return token

    escaped = re.sub(r"```([^\n`]*)\n(.*?)```", stash_code, escaped, flags=re.S)
    escaped = re.sub(r"`([^`]+)`", r'<code>\1</code>', escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)

    blocks = []
    current_list = []
    for raw_line in escaped.splitlines():
        line = raw_line.strip()
        if line.startswith("- ") or line.startswith("* "):
            current_list.append(f"<li>{line[2:]}</li>")
            continue
        if current_list:
            blocks.append("<ul>" + "".join(current_list) + "</ul>")
            current_list = []
        if not line:
            blocks.append('<div class="spacer"></div>')
        elif line.startswith("### "):
            blocks.append(f"<h4>{line[4:]}</h4>")
        elif line.startswith("## "):
            blocks.append(f"<h3>{line[3:]}</h3>")
        elif line.startswith("# "):
            blocks.append(f"<h2>{line[2:]}</h2>")
        elif line.startswith("@@CODEBLOCK"):
            blocks.append(line)
        else:
            blocks.append(f"<p>{line}</p>")
    if current_list:
        blocks.append("<ul>" + "".join(current_list) + "</ul>")

    rendered = "".join(blocks)
    for index, code in enumerate(code_blocks):
        rendered = rendered.replace(f"@@CODEBLOCK{index}@@", code)
    return rendered


def _find_pymol_main_window(QtWidgets):
    app = QtWidgets.QApplication.instance()
    if app is None:
        return None

    candidates = [widget for widget in app.topLevelWidgets() if isinstance(widget, QtWidgets.QMainWindow)]
    if not candidates:
        active = app.activeWindow()
        return active if isinstance(active, QtWidgets.QMainWindow) else None

    pymol_windows = [widget for widget in candidates if "pymol" in widget.windowTitle().lower()]
    pool = pymol_windows or candidates
    return max(pool, key=lambda widget: max(1, widget.width()) * max(1, widget.height()))


def _open_chat_window() -> None:
    global _chat_panel, _chat_container

    try:
        from pymol.Qt import QtCore, QtGui, QtWidgets
    except Exception as exc:
        print(f"DeepSeek: Qt not available ({exc}); use deepseek <request> instead.")
        return

    if _chat_container is not None:
        try:
            _chat_container.show()
            _chat_container.raise_()
            if hasattr(_chat_container, "activateWindow"):
                _chat_container.activateWindow()
            if _chat_panel is not None:
                _chat_panel.focus_prompt()
            return
        except RuntimeError:
            _chat_container = None
            _chat_panel = None

    class _Emitter(QtCore.QObject):
        event = QtCore.Signal(str, str)
        done = QtCore.Signal()
        undo_done = QtCore.Signal()

    class _PromptEdit(QtWidgets.QTextEdit):
        sendRequested = QtCore.Signal()

        def keyPressEvent(self, event):
            if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                if not (event.modifiers() & QtCore.Qt.ShiftModifier):
                    self.sendRequested.emit()
                    return
            super().keyPressEvent(event)

    class _AssistantPanel(QtWidgets.QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._emitter = _Emitter()
            self._emitter.event.connect(self._handle_event)
            self._emitter.done.connect(self._on_done)
            self._emitter.undo_done.connect(self._on_undo_done)
            self._build_ui()
            self._show_welcome()

        def _build_ui(self):
            self.setMinimumSize(620, 300)
            root = QtWidgets.QVBoxLayout(self)
            root.setContentsMargins(10, 8, 10, 8)
            root.setSpacing(7)

            header = QtWidgets.QHBoxLayout()
            title = QtWidgets.QLabel("<b>DeepSeek Assistant</b>")
            title.setToolTip(f"PyMOL DeepSeek Plugin v{_PLUGIN_VERSION}")
            self._status = QtWidgets.QLabel("Ready")
            self._status.setObjectName("DeepSeekStatus")
            self._context = QtWidgets.QLabel("")
            self._context.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self._context.setStyleSheet("color: palette(mid); font-size: 11px;")
            self._turns_label = QtWidgets.QLabel("Turn limit")
            self._turns_spin = QtWidgets.QSpinBox()
            self._turns_spin.setRange(0, 1000)
            self._turns_spin.setSpecialValueText("Unlimited")
            self._turns_spin.setValue(_get_max_tool_turns())
            self._turns_spin.setFixedWidth(82)
            self._turns_spin.setToolTip(
                "Maximum AI → tool → AI turns per message. Set 0 for unlimited; changes apply to the next message."
            )
            self._turns_spin.valueChanged.connect(self._apply_turn_limit)
            self._turns_spin.editingFinished.connect(self._announce_turn_limit)
            self._settings_btn = QtWidgets.QPushButton("Model settings…")
            self._settings_btn.clicked.connect(self._open_settings)
            header.addWidget(title)
            header.addSpacing(8)
            header.addWidget(self._status)
            header.addStretch(1)
            header.addWidget(self._context)
            header.addSpacing(8)
            header.addWidget(self._turns_label)
            header.addWidget(self._turns_spin)
            header.addWidget(self._settings_btn)
            root.addLayout(header)

            self._tabs = QtWidgets.QTabWidget()
            self._chat = QtWidgets.QTextBrowser()
            self._chat.setOpenExternalLinks(False)
            self._chat.setReadOnly(True)
            self._log = QtWidgets.QPlainTextEdit()
            self._log.setReadOnly(True)
            fixed_font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
            fixed_font.setPointSize(max(9, fixed_font.pointSize()))
            self._log.setFont(fixed_font)
            self._tabs.addTab(self._chat, "Chat")
            self._tabs.addTab(self._log, "Tool log")
            root.addWidget(self._tabs, 1)

            quick = QtWidgets.QHBoxLayout()
            quick.setSpacing(5)
            for label, prompt in (
                ("Structure overview", "Summarize the structures, chains, ligands, and main objects in the current PyMOL session."),
                ("Improve display", "Improve the current structure display: show proteins as cartoons, ligands as sticks, and choose suitable colors and a useful view."),
                ("Ligand pocket", "Identify the main ligand and show binding-pocket residues within 5 Å."),
                ("Align structures", "Align the two main protein objects in the current session and report the RMSD."),
            ):
                button = QtWidgets.QToolButton()
                button.setText(label)
                button.setToolTip(prompt)
                button.clicked.connect(lambda _checked=False, p=prompt: self._set_prompt(p))
                quick.addWidget(button)
            quick.addStretch(1)
            root.addLayout(quick)

            self._prompt = _PromptEdit()
            self._prompt.setAcceptRichText(False)
            self._prompt.setPlaceholderText(
                "Enter a natural-language instruction, for example: show the ligand as sticks and highlight residues within 5 Å\n"
                "Enter to send; Shift+Enter for a new line"
            )
            self._prompt.setMinimumHeight(70)
            self._prompt.setMaximumHeight(150)
            self._prompt.sendRequested.connect(self._send)
            root.addWidget(self._prompt)

            controls = QtWidgets.QHBoxLayout()
            self._send_btn = QtWidgets.QPushButton("Send")
            self._send_btn.setDefault(True)
            self._send_btn.clicked.connect(self._send)
            self._stop_btn = QtWidgets.QPushButton("Stop")
            self._stop_btn.setEnabled(False)
            self._stop_btn.clicked.connect(deepseek_stop_command)
            self._new_btn = QtWidgets.QPushButton("New chat")
            self._new_btn.clicked.connect(self._new_conversation)
            self._save_btn = QtWidgets.QPushButton("Save transcript")
            self._save_btn.clicked.connect(self._save)
            self._unsafe = QtWidgets.QCheckBox("Enable unrestricted Python (high risk)")
            self._unsafe.setChecked(_unsafe_enabled())
            self._unsafe.toggled.connect(self._toggle_unsafe)
            self._undo_btn = QtWidgets.QPushButton("Undo latest changes")
            self._undo_btn.setEnabled(_last_session_snapshot is not None)
            self._undo_btn.clicked.connect(self._undo)

            controls.addWidget(self._send_btn)
            controls.addWidget(self._stop_btn)
            controls.addWidget(self._new_btn)
            controls.addWidget(self._save_btn)
            controls.addStretch(1)
            controls.addWidget(self._unsafe)
            controls.addWidget(self._undo_btn)
            root.addLayout(controls)

            self._apply_chat_style()
            self._refresh_context_label()

        def _apply_chat_style(self):
            palette = self.palette()
            base = palette.color(QtGui.QPalette.Base).name()
            text_color = palette.color(QtGui.QPalette.Text).name()
            alternate = palette.color(QtGui.QPalette.AlternateBase).name()
            border = palette.color(QtGui.QPalette.Mid).name()
            self._chat.document().setDefaultStyleSheet(
                f"""
                body {{ background:{base}; color:{text_color}; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei',sans-serif; font-size:13px; }}
                .row {{ margin:8px 4px; }}
                .bubble {{ border:1px solid {border}; border-radius:9px; padding:8px 10px; }}
                .assistant {{ background:{alternate}; margin-right:60px; }}
                .user {{ background:#2563eb; color:white; margin-left:80px; }}
                .system {{ color:#777; font-size:11px; margin:4px 8px; }}
                .error {{ background:#fff0ed; color:#a12718; border:1px solid #d77a6b; border-radius:7px; padding:7px 9px; }}
                .name {{ font-size:11px; font-weight:600; margin-bottom:4px; }}
                p {{ margin:3px 0; }}
                ul {{ margin:4px 0 4px 20px; }}
                h2,h3,h4 {{ margin:7px 0 4px 0; }}
                code {{ font-family:monospace; background:rgba(127,127,127,.16); padding:1px 3px; border-radius:3px; }}
                pre.code {{ font-family:monospace; white-space:pre-wrap; background:rgba(127,127,127,.14); border-radius:6px; padding:8px; }}
                .lang {{ display:block; color:#777; font-size:10px; }}
                .spacer {{ height:4px; }}
                """
            )

        def _show_welcome(self):
            self._append_html(
                '<div class="row"><div class="bubble assistant">'
                '<div class="name">DeepSeek</div>'
                '<p>I am connected to the current PyMOL session. Describe the result you want, '
                'or ask me to select, measure, align, analyze, and run commands.</p>'
                '<p><b>Example:</b> “Show the protein as a cartoon, color it by chain, and display the ligand as sticks.”</p>'
                '</div></div>'
            )

        def _append_html(self, fragment: str):
            cursor = self._chat.textCursor()
            cursor.movePosition(QtGui.QTextCursor.End)
            cursor.insertHtml(fragment)
            cursor.insertBlock()
            self._chat.setTextCursor(cursor)
            self._chat.ensureCursorVisible()

        def _append_user(self, text: str):
            body = _markdown_to_html(text)
            self._append_html(
                f'<div class="row"><div class="bubble user"><div class="name">You</div>{body}</div></div>'
            )

        def _append_assistant(self, text: str):
            body = _markdown_to_html(text)
            self._append_html(
                f'<div class="row"><div class="bubble assistant"><div class="name">DeepSeek</div>{body}</div></div>'
            )

        def _append_system(self, text: str):
            self._append_html(f'<div class="system">{html.escape(text)}</div>')

        def _append_error(self, text: str):
            body = _markdown_to_html(text)
            self._append_html(f'<div class="row"><div class="error">{body}</div></div>')

        def _append_log(self, prefix: str, text: str):
            stamp = datetime.now().strftime("%H:%M:%S")
            self._log.appendPlainText(f"[{stamp}] {prefix}{text}")
            bar = self._log.verticalScrollBar()
            bar.setValue(bar.maximum())

        def emit_event(self, kind: str, text: str):
            self._emitter.event.emit(kind, text)

        def emit_done(self):
            self._emitter.done.emit()

        def _handle_event(self, kind: str, text: str):
            if kind == "assistant":
                self._append_assistant(text)
            elif kind == "status":
                self._status.setText(text)
                if text not in {"Ready"}:
                    self._append_system(text)
            elif kind == "tool":
                self._status.setText(text)
                self._append_log("Tool:", text)
            elif kind == "command":
                self._append_log("PyMOL> ", text)
            elif kind == "result":
                self._append_log("Result:", text)
            elif kind == "error":
                self._status.setText("Error")
                self._append_error(text)
                self._append_log("Error:", text)
            elif kind == "snapshot":
                self._undo_btn.setEnabled(text == "ready")
            self._refresh_context_label()

        def _send(self):
            query = self._prompt.toPlainText().strip()
            if not query or _is_running:
                return
            self._prompt.clear()
            self._append_user(query)
            self._status.setText("Preparing…")
            self._set_busy(True)
            self._tabs.setCurrentWidget(self._chat)
            _dispatch_deepseek(query, out_fn=self.emit_event, done_fn=self.emit_done)

        def _set_busy(self, busy: bool):
            self._send_btn.setEnabled(not busy)
            self._stop_btn.setEnabled(busy)
            self._prompt.setEnabled(not busy)
            self._new_btn.setEnabled(not busy)
            self._settings_btn.setEnabled(not busy)
            self._turns_spin.setEnabled(not busy)

        def _on_done(self):
            self._set_busy(False)
            if self._status.text() not in {"Error", "Stopped."}:
                self._status.setText("Ready")
            self._undo_btn.setEnabled(_last_session_snapshot is not None)
            self._refresh_context_label()
            self.focus_prompt()

        def _new_conversation(self):
            if _is_running:
                return
            _history.clear()
            self._chat.clear()
            self._log.clear()
            self._show_welcome()
            self._append_system("Started a new chat. The current PyMOL structures were not cleared.")
            self._status.setText("Ready")
            self.focus_prompt()

        def _set_prompt(self, text: str):
            self._prompt.setPlainText(text)
            self.focus_prompt()

        def focus_prompt(self):
            self._prompt.setFocus()

        def _refresh_context_label(self):
            try:
                objects = cmd.get_names("objects")
                atoms = sum(cmd.count_atoms(obj) for obj in objects[:20])
                suffix = "+" if len(objects) > 20 else ""
                self._context.setText(
                    f"{len(objects)} objects · {atoms}{suffix} atoms · {_get_model()}"
                )
            except Exception:
                self._context.setText(_get_model())

        def _apply_turn_limit(self, value: int):
            _set_max_tool_turns(value)

        def _announce_turn_limit(self):
            value = _get_max_tool_turns()
            label = "Unlimited" if value == 0 else f"{value} turns"
            self._append_system(f"Tool-call turn limit set to {label}. The change applies to the next message.")

        def _toggle_unsafe(self, checked: bool):
            if checked:
                answer = QtWidgets.QMessageBox.warning(
                    self,
                    "Enable unrestricted Python",
                    "When enabled, model-generated Python or PyMOL commands may read or modify local files and run system commands.\n\n"
                    "Enable this only when you understand the risk and trust the current task.",
                    QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel,
                    QtWidgets.QMessageBox.Cancel,
                )
                if answer != QtWidgets.QMessageBox.Ok:
                    self._unsafe.blockSignals(True)
                    self._unsafe.setChecked(False)
                    self._unsafe.blockSignals(False)
                    return
            _set_unsafe_enabled(checked)
            self._append_system("Unrestricted Python is enabled." if checked else "Safe Python mode has been restored.")

        def _undo(self):
            if _is_running or _last_session_snapshot is None:
                return
            answer = QtWidgets.QMessageBox.question(
                self,
                "Undo AI changes",
                "Restore the complete PyMOL state from before the latest AI operation?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.Yes,
            )
            if answer != QtWidgets.QMessageBox.Yes:
                return
            self._set_busy(True)
            self._undo_btn.setEnabled(False)
            thread = threading.Thread(
                target=_restore_snapshot,
                kwargs={"out_fn": self.emit_event, "done_fn": self._emitter.undo_done.emit},
                daemon=True,
            )
            thread.start()

        def _on_undo_done(self):
            self._set_busy(False)
            self._undo_btn.setEnabled(_last_session_snapshot is not None)
            self._refresh_context_label()
            self.focus_prompt()

        def _open_settings(self):
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("DeepSeek model settings")
            dialog.setMinimumWidth(470)
            form = QtWidgets.QFormLayout(dialog)

            model = QtWidgets.QComboBox()
            model.setEditable(True)
            model.addItems(["deepseek-v4-flash", "deepseek-v4-pro"])
            model.setCurrentText(_get_model())

            thinking = QtWidgets.QComboBox()
            thinking.addItem("Non-reasoning mode (faster; suitable for most PyMOL operations)", "disabled")
            thinking.addItem("Reasoning mode (complex analysis)", "enabled")
            thinking.setCurrentIndex(1 if _get_thinking_mode() == "enabled" else 0)

            base_url = QtWidgets.QLineEdit(_get_base_url())
            api_key = QtWidgets.QLineEdit()
            api_key.setEchoMode(QtWidgets.QLineEdit.Password)
            api_key.setPlaceholderText("Leave blank to keep the current API key")

            max_turns = QtWidgets.QSpinBox()
            max_turns.setRange(0, 1000)
            max_turns.setSpecialValueText("Unlimited")
            max_turns.setValue(_get_max_tool_turns())
            max_turns.setToolTip("0 means unlimited tool-call turns.")

            form.addRow("Model", model)
            form.addRow("Reasoning mode", thinking)
            form.addRow("Maximum tool-call turns", max_turns)
            form.addRow("Base URL", base_url)
            form.addRow("API Key", api_key)

            note = QtWidgets.QLabel(
                "Settings are stored in ~/.pymol/deepseek_config.json; the API key is stored separately in deepseek_key."
            )
            note.setWordWrap(True)
            form.addRow(note)

            buttons = QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)

            if dialog.exec_():
                chosen_model = model.currentText().strip() or _DEFAULT_MODEL
                chosen_base = base_url.text().strip().rstrip("/") or _DEFAULT_BASE_URL
                chosen_thinking = thinking.currentData()
                chosen_max_turns = int(max_turns.value())
                _write_config(
                    {
                        "model": chosen_model,
                        "base_url": chosen_base,
                        "thinking": chosen_thinking,
                        "max_tool_turns": chosen_max_turns,
                    }
                )
                os.environ["DEEPSEEK_MODEL"] = chosen_model
                os.environ["DEEPSEEK_BASE_URL"] = chosen_base
                os.environ["DEEPSEEK_THINKING"] = chosen_thinking
                os.environ["DEEPSEEK_MAX_TOOL_TURNS"] = str(chosen_max_turns)
                self._turns_spin.blockSignals(True)
                self._turns_spin.setValue(chosen_max_turns)
                self._turns_spin.blockSignals(False)
                if api_key.text().strip():
                    _save_api_key(api_key.text().strip())
                self._refresh_context_label()
                turns_label = "Unlimited" if chosen_max_turns == 0 else f"{chosen_max_turns} turns"
                self._append_system(f"Model settings updated: {chosen_model}; tool-call turn limit: {turns_label}.")

        def _save(self):
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            default_path = os.path.join(os.path.expanduser("~"), f"deepseek_chat_{timestamp}.html")
            path, _selected = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Save DeepSeek chat",
                default_path,
                "HTML files (*.html);;Text files (*.txt);;All files (*)",
            )
            if not path:
                return
            try:
                if path.lower().endswith(".txt"):
                    content = self._chat.toPlainText() + "\n\n--- Tool log ---\n" + self._log.toPlainText()
                else:
                    content = (
                        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
                        "<title>DeepSeek PyMOL Chat</title></head><body>"
                        + self._chat.toHtml()
                        + "<h2>Tool log</h2><pre>"
                        + html.escape(self._log.toPlainText())
                        + "</pre></body></html>"
                    )
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(content)
                self._append_system(f"Saved to {path}")
            except Exception as exc:
                self._append_error(f"Save failed: {exc}")

    main_window = _find_pymol_main_window(QtWidgets)
    panel = _AssistantPanel()
    _chat_panel = panel

    if main_window is not None:
        dock = QtWidgets.QDockWidget("DeepSeek Assistant", main_window)
        dock.setObjectName("DeepSeekAssistantDock")
        dock.setWidget(panel)
        dock.setMinimumHeight(280)
        try:
            allowed = (
                QtCore.Qt.BottomDockWidgetArea
                | QtCore.Qt.LeftDockWidgetArea
                | QtCore.Qt.RightDockWidgetArea
            )
            dock.setAllowedAreas(allowed)
            main_window.addDockWidget(QtCore.Qt.BottomDockWidgetArea, dock)
        except Exception:
            main_window.addDockWidget(QtCore.Qt.BottomDockWidgetArea, dock)

        # When PyMOL exposes its console as a dock, put the assistant beside it as a tab.
        try:
            for other in main_window.findChildren(QtWidgets.QDockWidget):
                if other is dock:
                    continue
                marker = (other.windowTitle() + " " + other.objectName()).lower()
                if any(word in marker for word in ("console", "command", "console")):
                    main_window.tabifyDockWidget(other, dock)
                    break
        except Exception:
            pass

        dock.show()
        dock.raise_()
        _chat_container = dock
    else:
        # Robust fallback for PyMOL builds whose main QMainWindow is not discoverable.
        window = QtWidgets.QMainWindow()
        window.setWindowTitle("DeepSeek Assistant — PyMOL")
        window.setCentralWidget(panel)
        window.resize(920, 650)
        window.show()
        window.raise_()
        window.activateWindow()
        _chat_container = window

    panel.focus_prompt()


# ---------------------------------------------------------------------------
# Single-question fallback
# ---------------------------------------------------------------------------


def _open_deepseek_dialog() -> None:
    try:
        from pymol.Qt import QtWidgets

        text, ok = QtWidgets.QInputDialog.getMultiLineText(
            QtWidgets.QApplication.activeWindow(),
            "DeepSeek AI",
            "Enter a natural-language question or PyMOL instruction:",
        )
        if ok and text.strip():
            _dispatch_deepseek(text.strip())
    except Exception as exc:
        print(f"DeepSeek: could not open dialog ({exc})")


# ---------------------------------------------------------------------------
# PyMOL command entry points
# ---------------------------------------------------------------------------


def deepseek_command(query: str = "") -> None:
    if str(query).strip():
        _dispatch_deepseek(str(query))
    else:
        _open_deepseek_dialog()


def deepseek_chat_command(_="") -> None:
    _open_chat_window()


def deepseek_stop_command(_="") -> None:
    if _is_running:
        _stop_event.set()
        print("DeepSeek: stop requested; the current API call may finish first.")
    else:
        print("DeepSeek: nothing is running.")


def deepseek_reset_command(_="") -> None:
    _history.clear()
    if _chat_panel is not None:
        try:
            _chat_panel._new_conversation()
        except Exception:
            pass
    print("DeepSeek: conversation history cleared.")


def deepseek_undo_command(_="") -> None:
    if _is_running:
        print("DeepSeek: stop the current task before undoing.")
        return
    threading.Thread(target=_restore_snapshot, daemon=True).start()


def deepseek_save_command(path: str = "") -> None:
    if _chat_panel is None:
        print("DeepSeek: open deepseek_chat first.")
        return
    if path:
        try:
            if str(path).lower().endswith(".txt"):
                content = _chat_panel._chat.toPlainText() + "\n\n--- Tool log ---\n" + _chat_panel._log.toPlainText()
            else:
                content = _chat_panel._chat.toHtml()
            with open(str(path), "w", encoding="utf-8") as handle:
                handle.write(content)
            print(f"DeepSeek: conversation saved to {path}")
        except Exception as exc:
            print(f"DeepSeek: save failed — {exc}")
    else:
        _chat_panel._save()


def deepseek_model_command(model: str = "") -> None:
    model = str(model).strip()
    if model:
        os.environ["DEEPSEEK_MODEL"] = model
        _write_config({"model": model})
        print(f"DeepSeek: model set to {model}")
        if _chat_panel is not None:
            try:
                _chat_panel._refresh_context_label()
            except Exception:
                pass
    else:
        print(f"DeepSeek: current model is {_get_model()}")


def deepseek_turns_command(turns: str = "") -> None:
    """Show or change the per-request tool-call turn limit. Use 0 for unlimited."""
    value = str(turns).strip()
    if value:
        try:
            chosen = _set_max_tool_turns(int(value))
        except ValueError:
            print("DeepSeek: usage: deepseek_turns <0-1000>; 0 means unlimited.")
            return
        label = "unlimited" if chosen == 0 else str(chosen)
        print(f"DeepSeek: maximum tool-call turns set to {label}.")
        if _chat_panel is not None:
            try:
                _chat_panel._turns_spin.blockSignals(True)
                _chat_panel._turns_spin.setValue(chosen)
                _chat_panel._turns_spin.blockSignals(False)
            except Exception:
                pass
    else:
        current = _get_max_tool_turns()
        print("DeepSeek: maximum tool-call turns: " + ("unlimited" if current == 0 else str(current)))


def deepseek_status_command(_="") -> None:
    key_source = "environment" if os.environ.get("DEEPSEEK_API_KEY", "").strip() else (
        _KEY_FILE if os.path.exists(_KEY_FILE) else "not configured"
    )
    print(f"DeepSeek plugin version: {_PLUGIN_VERSION}")
    print(f"DeepSeek model: {_get_model()}")
    print(f"DeepSeek thinking mode: {_get_thinking_mode()}")
    max_turns = _get_max_tool_turns()
    print("DeepSeek maximum tool-call turns: " + ("unlimited" if max_turns == 0 else str(max_turns)))
    print(f"DeepSeek base URL: {_get_base_url()}")
    print(f"DeepSeek API key source: {key_source}")
    print("Unrestricted Python: " + ("enabled" if _unsafe_enabled() else "disabled"))
    print("Rollback snapshot: " + ("available" if _last_session_snapshot is not None else "none"))


def install_deepseek_deps(_="") -> None:
    print(f"Installing OpenAI SDK into {sys.executable} ...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "openai"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("OpenAI SDK installed successfully. Restart PyMOL if import still fails.")
    else:
        print(f"pip failed:\n{result.stderr}")


# Optional Plugin menu entry when installed through PyMOL Plugin Manager.
def __init_plugin__(app=None):
    try:
        from pymol.plugins import addmenuitemqt

        addmenuitemqt("DeepSeek Assistant", _open_chat_window)
    except Exception:
        pass


cmd.extend("deepseek", deepseek_command)
cmd.extend("deepseek_chat", deepseek_chat_command)
cmd.extend("deepseek_stop", deepseek_stop_command)
cmd.extend("deepseek_reset", deepseek_reset_command)
cmd.extend("deepseek_undo", deepseek_undo_command)
cmd.extend("deepseek_save", deepseek_save_command)
cmd.extend("deepseek_model", deepseek_model_command)
cmd.extend("deepseek_turns", deepseek_turns_command)
cmd.extend("deepseek_status", deepseek_status_command)
cmd.extend("install_deepseek_deps", install_deepseek_deps)

try:
    cmd.set_key("F2", _open_chat_window)
except Exception:
    pass

print(f"DeepSeek plugin v{_PLUGIN_VERSION} loaded.")
print("  • deepseek_chat   open the docked assistant (or press F2)")
print("  • deepseek_undo   restore the state before the latest AI turn")
print("  • deepseek_stop   cancel a running request")
print("  • deepseek_turns set tool-call turn limit; 0 means unlimited")
print("  • deepseek_status show configuration")

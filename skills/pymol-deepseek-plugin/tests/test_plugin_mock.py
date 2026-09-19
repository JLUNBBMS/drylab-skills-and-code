import importlib.util
from pathlib import Path
import json
import os
import sys
import types
from types import SimpleNamespace


class FakeCmd:
    def __init__(self):
        self.commands = []
        self.extensions = {}
        self.restored_session = None

    def get_names(self, kind):
        return ["protein"] if kind == "objects" else []

    def get_chains(self, obj):
        return ["A"]

    def count_atoms(self, obj):
        return 42

    def get_state(self):
        return 1

    def get_session(self):
        return {"names": ["snapshot"]}

    def set_session(self, session):
        self.restored_session = session

    def do(self, command):
        self.commands.append(command)

    def extend(self, name, fn):
        self.extensions[name] = fn

    def set_key(self, key, fn):
        self.key = (key, fn)


os.environ["DEEPSEEK_MAX_TOOL_TURNS"] = "12"

fake_cmd = FakeCmd()
pymol = types.ModuleType("pymol")
pymol.cmd = fake_cmd
pymol.stored = SimpleNamespace()
sys.modules["pymol"] = pymol

responses = [
    SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content="I will style and inspect the structure.",
        reasoning_content=None,
        tool_calls=[
            SimpleNamespace(id="call_1", function=SimpleNamespace(
                name="execute_pymol_commands",
                arguments=json.dumps({
                    "commands": ["show cartoon, protein", "color cyan, protein"],
                    "explanation": "Styling the protein.",
                }),
            )),
            SimpleNamespace(id="call_2", function=SimpleNamespace(
                name="run_python_analysis",
                arguments=json.dumps({
                    "code": "print(cmd.count_atoms('protein'))",
                    "explanation": "Counting atoms.",
                }),
            )),
        ],
    ))]),
    SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content="Done. The protein has 42 atoms.",
        reasoning_content=None,
        tool_calls=None,
    ))]),
]


class FakeCompletions:
    def create(self, **kwargs):
        assert kwargs["model"] == "deepseek-v4-flash"
        assert kwargs["tools"][0]["type"] == "function"
        assert kwargs["extra_body"]["thinking"]["type"] == "disabled"
        return responses.pop(0)


class FakeOpenAIClient:
    def __init__(self, **kwargs):
        assert kwargs["base_url"] == "https://api.deepseek.com"
        self.chat = SimpleNamespace(completions=FakeCompletions())


openai = types.ModuleType("openai")
openai.OpenAI = FakeOpenAIClient
sys.modules["openai"] = openai

plugin_path = Path(__file__).resolve().parents[1] / "pymol_deepseek_plugin.py"
spec = importlib.util.spec_from_file_location("pymol_deepseek_plugin", plugin_path)
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)

out = []
assert plugin._get_max_tool_turns() == 12
plugin._run_deepseek("style it", "test-key", out_fn=out.append)

assert fake_cmd.commands == ["show cartoon, protein", "color cyan, protein"]
assert any(message.get("role") == "tool" and "42" in message.get("content", "") for message in plugin._history)
assert out[-1] == "DeepSeek: Ready"
assert plugin._last_session_snapshot == {"names": ["snapshot"]}

plugin._restore_snapshot(out_fn=out.append)
assert fake_cmd.restored_session == {"names": ["snapshot"]}
assert plugin._last_session_snapshot is None

required = {
    "deepseek",
    "deepseek_chat",
    "deepseek_stop",
    "deepseek_reset",
    "deepseek_undo",
    "deepseek_save",
    "deepseek_model",
    "deepseek_turns",
    "deepseek_status",
    "install_deepseek_deps",
}
assert required.issubset(fake_cmd.extensions)
print("PASS")
print("\n".join(out))

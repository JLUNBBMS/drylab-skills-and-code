# DeepSeek Assistant for PyMOL

Control the current PyMOL session with natural language. The plugin sends structural context to DeepSeek, lets the model call controlled PyMOL commands and structure-analysis tools, and executes approved operations directly in PyMOL.

> Current version: **3.1.0**  
> Project status: testing preview. Use a copy of non-critical structures first and review the tool log.

## Features

- Dockable, resizable chat panel embedded in PyMOL
- Separate chat and tool-execution logs
- Multi-turn context, task cancellation, and transcript export
- Quick actions for structure summaries, display cleanup, ligand pockets, and alignment
- Automatic PyMOL session snapshot before each operation, with one-click undo
- Configurable maximum tool-call turns per message; `0` means unlimited
- DeepSeek V4 Flash/Pro, reasoning mode, Base URL, and API-key configuration
- System commands, local scripts, and unrestricted Python blocked by default

## Examples

```text
Show the current protein as a cartoon, color it by chain, and display the ligand as sticks.
```

```text
Identify the main ligand, show residues within 5 Å as sticks, and label the residue names.
```

```text
Align the two current protein objects, report the RMSD, and color regions with larger differences.
```

## Requirements

- PyMOL 2.x or 3.x with the Qt GUI
- Python 3
- A DeepSeek API key
- `openai>=1.30.0`

The DeepSeek API uses an OpenAI-compatible interface. The default Base URL is `https://api.deepseek.com`. The default model is `deepseek-v4-flash`; `deepseek-v4-pro` is also available.

## Installation

### Plugin Manager

1. Download `pymol_deepseek_plugin.py` from the repository root.
2. In PyMOL, open `Plugin > Plugin Manager > Install New Plugin`.
3. Select the file and allow it to replace an older version.
4. Exit PyMOL completely and restart it.
5. Run `deepseek_chat` or press `F2`.

### Manual installation

macOS / Linux:

```bash
mkdir -p ~/.pymol/startup/
cp pymol_deepseek_plugin.py ~/.pymol/startup/pymol_deepseek_plugin.py
```

Typical Windows path:

```text
%USERPROFILE%\.pymol\startup\pymol_deepseek_plugin.py
```

## API key

When you send the first message, the plugin prompts for an API key and stores it at:

```text
~/.pymol/deepseek_key
```

You can also use an environment variable:

```bash
export DEEPSEEK_API_KEY="your_API_key"
```

Windows PowerShell:

```powershell
$env:DEEPSEEK_API_KEY="your_API_key"
```

The configuration file is stored at:

```text
~/.pymol/deepseek_config.json
```

These local files are excluded from version control.

## Tool-call turns

The **Turn limit** controls the agent loop for one natural-language request. It is not a chat-message limit.

- Default: `12`
- Recommended for complex tasks: `30–50`
- `0`: unlimited; stop the task manually if the agent loops

Command-line configuration:

```text
deepseek_turns 30
deepseek_turns 0
deepseek_turns
```

## PyMOL commands

| Command | Description |
|---|---|
| `deepseek_chat` | Open or focus the docked assistant |
| `deepseek <request>` | Run one request from the command line |
| `deepseek_stop` | Stop the current task |
| `deepseek_reset` | Clear conversation history without clearing structures |
| `deepseek_undo` | Restore the state from before the latest AI operation |
| `deepseek_save [path]` | Save the conversation transcript |
| `deepseek_model [model]` | View or change the model |
| `deepseek_turns [count]` | View or set the tool-call turn limit; `0` means unlimited |
| `deepseek_status` | Show configuration and version information |
| `install_deepseek_deps` | Install or upgrade the OpenAI SDK |

## Security

By default, the plugin blocks PyMOL commands that can directly execute local code or system commands, including `python`, `run`, `@`, `system`, `spawn`, and `exec`. The restricted Python analysis environment does not allow module imports, file I/O, or system commands.

Enable **Unrestricted Python (high risk)** only for explicitly trusted tasks. When enabled, model-generated code may access local files or run system commands.

Your API key and prompt content are sent to the configured DeepSeek API service. Do not include information that should not be shared with a third-party service.

## Development and testing

Run the mock tests without a real PyMOL installation or API key:

```bash
python tests/test_plugin_mock.py
```

Run the pre-release checks:

```bash
python scripts/check_release.py
```

## Troubleshooting

### The old small window still appears

Run:

```text
deepseek_status
```

Expected output:

```text
DeepSeek plugin version: 3.1.0
```

If the version is incorrect, remove older copies of the plugin, replace the file in `~/.pymol/startup/`, and restart PyMOL completely.

### The panel cannot dock in the main window

Some customized PyMOL builds do not expose the main `QMainWindow`. The plugin falls back to a standalone 920×650 window without losing functionality.

### OpenAI SDK installation fails

Run this in the PyMOL command line:

```text
install_deepseek_deps
```

Then restart PyMOL.

## Contributing and security reports

Read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting code. Report security issues privately as described in [SECURITY.md](SECURITY.md). Never post an API key in a public issue.

## License status

Before public release, read [LICENSE_PENDING.md](LICENSE_PENDING.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The archived upstream Claude project did not include a license, so this package does not claim an MIT, Apache, or other open-source license. Add a formal open-source license only after obtaining upstream permission or completing a demonstrably independent rewrite.

## Acknowledgements

The original concept was inspired by Darya Stepanenko's Claude AI Plugin for PyMOL. This version uses DeepSeek's OpenAI-compatible API and redesigns the docked interface, tool log, session undo, safety controls, and configurable agent loop.

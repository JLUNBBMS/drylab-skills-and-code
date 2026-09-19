# Changelog

All notable changes to this project are documented in this file.

## 3.1.0

- Added a **Turn limit** spin box at the top of the assistant panel
- Added support for `0 = unlimited`, with a range of 0–1000
- Persisted the turn limit in `deepseek_config.json`; changes apply from the next message
- Added the maximum tool-call turn setting to the model settings dialog
- Added the `deepseek_turns` command and status output
- Fixed a false limit warning when the model completed on the final allowed turn
- Removed `__pycache__` directories and compiled artifacts from release packages
- Added GitHub Actions, issue templates, contribution guidance, security documentation, and a release-check script

## 3.0.0

- Replaced the fixed small window with a `QDockWidget` inside the PyMOL main window
- Added automatic tabification with the PyMOL console when available
- Added separate chat and tool-log tabs
- Added multi-line input, quick prompts, a status bar, and session summaries
- Added graphical configuration for model, reasoning mode, Base URL, and API key
- Added a snapshot of the latest operation and one-click undo
- Added a high-risk unrestricted-Python switch with confirmation
- Added a Plugin menu entry
- Improved Markdown rendering, transcript export, and light/dark theme adaptation
- Added DeepSeek V4 `thinking` support with fallback compatibility for older SDKs

## 2.0.0

- Migrated from the Claude API to DeepSeek's OpenAI-compatible API
- Added tool calls, persistent conversation history, stop, save, status, and model commands
- Blocked high-risk PyMOL commands by default

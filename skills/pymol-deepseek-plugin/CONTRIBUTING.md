# Contributing

Thank you for helping improve DeepSeek Assistant for PyMOL.

## Development workflow

1. Fork the repository and create a feature branch.
2. Do not commit API keys, `.env` files, local PyMOL configuration, session files, or real private structure data.
3. Keep the plugin installable as a single file through the PyMOL Plugin Manager.
4. Add or update mock tests when changing the agent loop, command filtering, configuration loading, or UI behavior.
5. Run:

```bash
python tests/test_plugin_mock.py
python scripts/check_release.py
```

6. In the pull request, describe the problem, implementation, test results, PyMOL/OS versions, and any effect on security boundaries.

## Code principles

- Use secure defaults; dangerous capabilities must require explicit opt-in.
- Never print complete API keys in logs.
- Do not silently expand the commands the model may execute.
- Update the UI only from the Qt main thread.
- Preserve Windows, macOS, and Linux path compatibility.
- Explain why a new dependency is necessary before adding it; avoid making single-file installation fragile.

## Bug reports

Include reproducible steps, plugin version, PyMOL version, Python version, operating system, and redacted logs. Do not paste API keys or complete requests containing sensitive structural information.

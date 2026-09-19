# Release checklist

- [ ] Confirm upstream licensing or complete a documented independent rewrite
- [ ] Replace `LICENSE_PENDING.md` with a real `LICENSE`
- [ ] Configure a private vulnerability-reporting channel
- [ ] Run `python tests/test_plugin_mock.py`
- [ ] Run `python scripts/check_release.py`
- [ ] Test installation through PyMOL Plugin Manager on at least one supported platform
- [ ] Verify `deepseek_status`, `deepseek_chat`, stop, undo and tool-turn settings
- [ ] Confirm no API Key, `.env`, logs, private structures or local paths are included
- [ ] Tag the release as `v3.1.0`
- [ ] Attach the single plugin file and install ZIP to the GitHub Release

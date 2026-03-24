# TODO: P3-4.3 Plugin/Extension Mechanism

> **Status**: Pending (long-term roadmap)
> **Priority**: P3 (low)

## Goal

Allow projects to customize ADDS behavior via a plugin system.

## Proposed Design

### Plugin Discovery

ADDS would look for plugins in:
1. `.ai/plugins/` — project-level plugins
2. `~/.adds/plugins/` — user-level plugins

### Plugin Interface

Each plugin is a Python script implementing one or more hooks:

```python
# .ai/plugins/my_plugin.py

def on_feature_complete(feature_id: str, project_root: str) -> None:
    """Called when a feature is marked completed."""
    pass

def on_session_start(agent: str, feature_id: str) -> None:
    """Called at the start of each session."""
    pass

def on_archive(feature_id: str, archive_path: str) -> None:
    """Called when a feature is archived."""
    pass

def validate_feature(feature: dict) -> list:
    """Return list of validation errors for a feature."""
    return []
```

### Configuration

```yaml
# .ai/adds_config.yaml
plugins:
  - .ai/plugins/notify_slack.py
  - .ai/plugins/auto_tag.py
options:
  compress_threshold: 1000
  auto_archive: true
```

### CLI Integration

```bash
adds plugins list          # List loaded plugins
adds plugins run <hook>    # Manually trigger a hook
```

## Use Cases

- **Slack notifications** when features complete
- **Auto-tagging** git commits with feature IDs
- **Custom validation** rules for specific project types
- **Metrics export** to external dashboards
- **Integration** with issue trackers (Jira, Linear, GitHub Issues)

## Implementation Notes

- Keep plugins simple — Python scripts, no complex framework
- Plugins should be optional — ADDS works without any plugins
- Plugin errors should not block core ADDS operations
- Consider security: plugins run with project permissions

## References

- OpenSpec Profile system (P3-4.3 inspiration)
- ADDS security guidelines: docs/guide/05-security.md

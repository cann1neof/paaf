# Skill Authoring & Security

Skills extend PAAF assistants with `@tool` functions and system prompt persona fragments.

> **SECURITY NOTICE:** Skills run in-process with no sandbox; manifest permissions provide disclosure, not process isolation. For untrusted code, use MCP servers.

## Authoring a Skill

A skill directory requires a `skill.yaml` manifest:

```yaml
name: my_custom_skill
version: 1.0.0
description: Custom tools for task automation
tools:
  - my_tool
permissions:
  file_access: confirm
```

And python modules with `@tool` decorated functions:

```python
from paaf_llm.tools.decorator import tool

@tool(description="Execute custom operation")
def my_tool(param: str) -> str:
    return f"Processed {param}"
```

## Installing Skills

Install via git URL or local path:

```bash
paaf skill install https://github.com/example/my_skill.git
```

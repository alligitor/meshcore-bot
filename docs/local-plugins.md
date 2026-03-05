# Local plugins and services

You can add your own **command plugins** and **service plugins** without modifying the bot’s code by placing them in the **`local/`** directory. Their configuration can live in **`local/config.ini`** so it stays separate from the main `config.ini`.

## Directories

| Path | Purpose |
|------|---------|
| **local/commands/** | One Python file per command plugin (subclass of `BaseCommand`). |
| **local/service_plugins/** | One Python file per service plugin (subclass of `BaseServicePlugin`). |
| **local/config.ini** | Optional. Merged with main config; use it for your plugins’ sections. |

Local plugins are **additive**: they are loaded after built-in (and alternative) plugins. If a local plugin or service has the same logical **name** as one already loaded, it is **skipped** and a warning is logged. There is no override-by-name for local code.

## Minimal command plugin

Create a file in **local/commands/** (e.g. `local/commands/hello_local.py`):

```python
# local/commands/hello_local.py
from modules.commands.base_command import BaseCommand
from modules.models import MeshMessage


class HelloLocalCommand(BaseCommand):
    name = "hellolocal"
    keywords = ["hellolocal", "hi local"]
    description = "A local greeting command"

    async def execute(self, message: MeshMessage) -> bool:
        return await self.handle_keyword_match(message)
```

- The bot discovers all `.py` files in `local/commands/` (except `__init__.py`).
- Each file must define exactly one class that inherits from `BaseCommand` and is not the base class itself.
- Use `bot.config` for options; you can put your section in **local/config.ini** (e.g. `[HelloLocal_Command]`) and read with `self.get_config_value('HelloLocal_Command', 'enabled', fallback=True, value_type='bool')` or `self.bot.config.get(...)`.

Restart the bot (or ensure the directory exists and the file is in place before starting). The command will be registered like any other.

## Minimal service plugin

Create a file in **local/service_plugins/** (e.g. `local/service_plugins/my_background_service.py`):

```python
# local/service_plugins/my_background_service.py
from modules.service_plugins.base_service import BaseServicePlugin


class MyBackgroundService(BaseServicePlugin):
    config_section = "MyBackground"
    description = "A local background service"

    async def start(self) -> None:
        self._running = True
        self.logger.info("MyBackground service started")

    async def stop(self) -> None:
        self._running = False
        self.logger.info("MyBackground service stopped")
```

- The bot discovers all `.py` files in `local/service_plugins/` (excluding `__init__.py`, `base_service.py`, and `*_utils.py`).
- The class must inherit from `BaseServicePlugin` and implement `start()` and `stop()`.
- To enable it, add a section in **local/config.ini** (or main config) with `enabled = true`:

```ini
[MyBackground]
enabled = true
```

Restart the bot so the service is loaded and started.

## Configuration

- **Main config** is read first, then **local/config.ini** if it exists. So `bot.config` contains both; later file wins on overlapping sections/keys.
- Put options for your local plugins in **local/config.ini** to keep main `config.ini` clean. Use the same section naming as built-in plugins (e.g. `[MyCommand_Command]` for a command, or a `config_section` for a service).
- After a **config reload** (e.g. via the `reload` command), both main config and `local/config.ini` are re-read, so on-demand config in your plugins will see updates. Plugin/service instances are not reloaded; only config values.

## Duplicate names

If a local command or service has the same **name** as an already-loaded plugin or service (e.g. you add `local/commands/ping.py` with `name = "ping"`), the local one is **skipped** and a warning is logged. Choose a different name (e.g. `pinglocal`) to avoid the conflict.

## References

- [Service plugins](service-plugins.md) — built-in services and how they are enabled.
- [Check-in API](checkin-api.md) — contract for the optional check-in submission API (local check-in service).
- Built-in command plugins live in **modules/commands/** and **modules/commands/alternatives/**; you can use them as examples for `BaseCommand`, `get_config_value`, `handle_keyword_match`, etc.
- Base classes: **modules/commands/base_command.py** (`BaseCommand`), **modules/service_plugins/base_service.py** (`BaseServicePlugin`).

## Check-in service (local)

The repo includes a local service plugin **`local/service_plugins/checkin_service.py`** that collects check-ins from a channel (default `#meshmonday`) on a chosen day (Monday only or daily). You can require a specific phrase (e.g. "check in") or count any message. Optionally it submits check-in data (packet hash, username, message) to a web API secured with an API key. Configuration belongs in **local/config.ini** under `[CheckIn]`. See **config.ini.example** for a commented `[CheckIn]` block and **[Check-in API](checkin-api.md)** for the API contract if you run or build a server to receive submissions.

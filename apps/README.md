# Adding apps to DILARA

DILARA can be extended without editing `main.py` for simple integrations.

## Register through the UI

Open **Apps & Users** in the left sidebar. Enter an ID, display name, description, entry point and type:

- `python`: launches a Python script in a separate process after confirmation.
- `url`: opens an HTTP(S) URL using the system browser.
- `folder`: opens a local folder in the system file manager.

Registration does not execute code. Python apps are arbitrary code, so only register scripts you trust. Added apps appear in the **Available Apps** list at the bottom of D-LLM.

## Drop-in manifest

Create `apps/<your-app-id>/app.json`:

```json
{
  "id": "example-tool",
  "name": "Example Tool",
  "description": "Short description shown in DILARA",
  "kind": "python",
  "entrypoint": "C:/Path/To/example_tool.py",
  "enabled": true
}
```

Supported manifest `kind` values are `python`, `url`, and `folder`. DILARA only discovers the manifest; it does not execute it during startup. The user chooses when to launch it. Restart DILARA or reopen D-LLM to refresh the displayed list.

This first plugin interface is intentionally simple. A future version should define versioned APIs, permissions/capabilities, health checks, update management and process lifecycle hooks before supporting deeply embedded modules.

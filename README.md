# npm-updater-ai-cli
Updates Gemini CLI, Codex CLI and npm itself.

# Settings

```
AUTO_UPDATE_NPM: bool = True         # update npm first if newer
CONFIRM_BEFORE_UPDATE: bool = False  # ask before updates/installs
PAUSE_AT_END: bool = True            # keep window open at the end
```

# Output example

```
npm CLI Updater
This script checks global npm installations and updates when needed.

— npm itself —
Current npm version: 11.5.2
Latest npm version: 11.5.2
npm is current.

— Gemini CLI —
Current Gemini CLI version: 0.1.22
Latest Gemini CLI version: 0.1.22
Already up to date.

— OpenAI Codex CLI —
Current OpenAI Codex CLI version: 0.23.0
Latest OpenAI Codex CLI version: 0.23.0
Already up to date.

Done
All packages were checked.

Press Enter to exit …
```

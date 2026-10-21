# Multi-user sign-in, extensible apps, and D-LLM choices

## Local accounts

- First launch asks the operator to create the first administrator account.
- Passwords are stored as PBKDF2-HMAC-SHA256 verifiers with random salts (310,000 iterations), not plaintext.
- Users sign in to a local DILARA account; the desktop header identifies the current account and role.
- Desktop geometry and DSPACE/CYBERSTORM/EYE registries are kept under `data/users/<username>/` to avoid sharing these preferences/resources by default.
- Administrators can create additional `user` or `admin` accounts in **Apps & Users**.

This is application-level authentication. It does not create or authenticate Windows accounts and cannot protect files from another Windows user/admin who can read the project directory. This prototype does not yet include login throttling, recovery workflows, account deletion/disable controls, or a hardened secrets store. Use filesystem ACLs and Windows accounts for stronger isolation.

## D-LLM implementation status

- The intended D-LLM is the in-house chatbot/rough LLM implementation in `legacy_modules/DilaraLLM_demo-main/dilara_core.py`. It is a work in progress and is launched as a separate process to preserve its existing UI while it continues to evolve.
- DILARA does **not** require Ollama, a model pull, GGUF weights, or `llama.cpp` for its custom D-LLM route.
- `dilara_core_v2.py` is a separate legacy Ollama experiment. It is preserved for historical/reference purposes but is not presented as the D-LLM implementation and is not launched from the current D-LLM workspace.
- The built-in utility fallback is a separate lightweight, no-network helper for DILARA help and arithmetic. It is not a trained or generative LLM.
- Voice behavior in `dilara_core.py` is mixed: Vosk can perform speech recognition locally when its model is present; the optional SpeechRecognition fallback calls Google's online recognition service. Avoid that fallback when strict offline operation is required.

The D-LLM workspace ends with a human-readable list of built-in modules and registered added apps so the user can navigate to familiar tools without needing to understand internal IDs.

## Extensibility

Apps may be registered in the UI or discovered from `apps/<folder>/app.json`. Discovery does not execute code. Launching Python apps requires an explicit confirmation. Supported first-pass app types are Python child process, HTTP(S) URL, and local folder. Deeply embedded modules require a future versioned plugin API and permission model.

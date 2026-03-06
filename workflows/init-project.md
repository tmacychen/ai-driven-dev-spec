---
description: Initialization workflow for AI-driven development projects
---

# Project Initialization Workflow

// turbo-all

1. Create project directory and enter it.
2. Copy `templates/scaffold/` template folder to current project root directory.
3. Create `app_spec.md`, describing the application you want to build in detailed natural language (refer to `examples/app_spec_example.md`).
4. Load `templates/prompts/initializer_prompt.md` as system prompt (context).
5. Run AI command, requesting to start "Initializer Agent" mode, generating:
    - `CORE_GUIDELINES.md` (self-guiding core guide)
    - `progress.log` (human-readable progress log)
    - `.ai/feature_list.json` (including test_cases, security_checks, core markers)
    - `.ai/architecture.md` (technology stack, architecture, data flow)
6. Verify `init.sh` can run correctly: `chmod +x init.sh && bash init.sh`.
7. Initialize Git repository and make initial commit:
   ```bash
   git init
   git add .
   git commit -m "chore: initial project setup"
   ```
8. Verify each feature in `.ai/feature_list.json` includes `test_cases` field.
9. Output initialization report: total features, high/medium/low priority distribution, number of core features.
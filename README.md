# Atlassian AI Skills

A collection of **AI agent skills** for automating **Atlassian Data Center / Server**
administration (Jira, Confluence). Each skill is self‑contained, dependency‑free, and usable by
AI coding agents (Claude Code, Cursor, custom agents…) **and** by humans straight from the CLI.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Atlassian](https://img.shields.io/badge/Atlassian-Data%20Center%20%2F%20Server-0052CC)

---

## Skills catalog

| Skill | Description | Product |
|-------|-------------|---------|
| [`jira-workflow-layout`](jira-workflow-layout/) | Update / copy / auto‑arrange a workflow **diagram layout** (node positions + connector angles) via the Workflow Designer REST API. | Jira DC/Server |

> More skills will be added over time. Each lives in its own folder with a `README.md`,
> a `SKILL.md` manifest, and a standalone script.

## Repository layout

```
Atlassian-AI-Skills/
├── README.md                     ← you are here
├── LICENSE                       ← MIT
└── <skill-name>/
    ├── README.md                 ← full documentation for the skill
    ├── SKILL.md                  ← agent manifest (name + description + instructions)
    └── scripts/                  ← standalone, dependency‑free script(s)
```

## Using a skill

### With Claude Code
Copy a skill folder into your skills directory — it activates automatically when relevant:
```bash
cp -r <skill-name> ~/.claude/skills/        # personal (all projects)
# or per project:
cp -r <skill-name> <project>/.claude/skills/
```

### With other AI agents
Any agent that can run shell commands can use these skills:
1. Feed the skill's **`SKILL.md`** to the agent as its instruction manifest — it lists the inputs
   to collect from the user and the exact commands to run.
2. The agent calls the standalone script under `<skill-name>/scripts/`.

### As a human (plain CLI)
The scripts are normal Python 3 CLIs:
```bash
python3 <skill-name>/scripts/*.py --help
```

## Design principles

- **No dependencies** — Python standard library only; runs anywhere.
- **Secrets stay out** — tokens/credentials are requested at runtime, never stored in the repo.
- **Safe by default** — dry‑run first, back up before write, documented rollback.
- **Portable** — driven by a clear `SKILL.md` so any capable AI agent can use it, not just one vendor.

## Contributing

Contributions welcome. To add a skill:
1. Create `<skill-name>/` with `README.md`, `SKILL.md`, and `scripts/`.
2. Keep scripts dependency‑free and free of any secret or customer‑specific data.
3. Add a row to the catalog table above.

Open an issue or a pull request.

## Disclaimer

These tools interact with **internal/undocumented** Atlassian REST endpoints that may change
between product versions. They are **not affiliated with or endorsed by Atlassian**. Test in a
non‑production environment first, and review each skill's caveats. Use at your own risk.

## License

[MIT](LICENSE) © ramses2k

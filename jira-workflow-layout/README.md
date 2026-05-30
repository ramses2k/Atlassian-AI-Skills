# jira-workflow-layout

> Update, copy, or tidy the **diagram layout** of a Jira **Data Center / Server** workflow
> (node positions + connector angles) through the Workflow Designer's internal REST API —
> without touching steps, transitions, conditions, validators, post-functions or scripts.

**Status:** stable · **Version:** 1.0.0 · **Runtime:** Python 3 (standard library only)

---

## Why

The Jira workflow diagram layout (where each status box sits, how connectors attach) is **not**
stored in the OSWorkflow XML you export/import — it lives in the Workflow Designer, server‑side.
After importing a workflow, Jira auto‑arranges it, often producing overlapping nodes and labels.

This skill lets an AI agent (or a human) **programmatically reposition** the diagram:

- **Copy** a clean layout from one workflow to another (e.g. `WF_v2` → `WF_v3`) when both share the
  same step/action IDs.
- **Auto‑arrange** a single workflow into a tidy left‑to‑right grid (`grid`).
- **Apply** a hand‑crafted layout, and **back up / roll back** safely.

## How it works

The Workflow Designer reads and writes the layout via an internal REST API:

| Operation | Request |
|-----------|---------|
| Read  | `GET /rest/workflowDesigner/latest/workflows?name=<NAME>&draft=<bool>` |
| Write | `POST /rest/workflowDesigner/latest/workflows` |

Write body:
```json
{ "draft": false, "name": "<NAME>", "layout": { "statuses": [...], "transitions": [...], "loopedTransitionContainer": {"x":0,"y":0} } }
```
Required headers: `Authorization: Bearer <PAT>`, `Content-Type: application/json`, `X-Atlassian-Token: no-check`.

**Layout format**
- `statuses`: `[{ "id": "S<stepId>" | "I<1>", "x": <px>, "y": <px> }]` — `I<1>` is the initial node.
- `transitions`: `[{ "id": "A<actionId:src:tgt>", "sourceAngle": <deg>, "targetAngle": <deg>, "sourceId": "S<..>", "targetId": "S<..>" }]`
  - angles in degrees, `0° = east`, `90° = up`; `sourceId`/`targetId` omitted for looped transitions.
- `loopedTransitionContainer`: `{ "x": <px>, "y": <px> }`.

Node/transition IDs are **stable across workflow copies**, which is why `copy` works between two
workflows that have identical steps and transitions.

## Prerequisites

1. **Jira Data Center / Server** (this internal API does not exist on Jira Cloud).
2. A Jira **Personal Access Token** belonging to a **workflow administrator**
   (*Profile → Personal Access Tokens*).
3. Python 3.8+ available to the agent/host.

## Installation

### Claude Code (Agent Skill)
Copy this folder into your skills directory:
```bash
cp -r jira-workflow-layout ~/.claude/skills/          # personal (all projects)
# or, per project:
cp -r jira-workflow-layout <project>/.claude/skills/
```
The skill auto‑activates when you ask to clean up / copy / rearrange a Jira workflow diagram.
`SKILL.md` is the Claude manifest (name + description + instructions).

### Other AI agents (Cursor, Copilot agents, custom tools…)
Any agent that can run shell commands can use this skill:
1. Point the agent at **`SKILL.md`** as the instruction manifest (it describes the inputs to
   collect and the commands to run).
2. The agent invokes the standalone CLI `scripts/layout_tool.py`.

### Humans (plain CLI)
```bash
python3 jira-workflow-layout/scripts/layout_tool.py --help
```

## Usage

The tool collects three inputs (the agent should **ask the user** for them):
**source workflow URL**, **target workflow URL**, and the **admin PAT**.
You pass the Workflow Designer URLs directly — the base URL, workflow name (`wfName`) and
live/draft mode (`workflowMode`) are parsed automatically.

```bash
TOOL="python3 jira-workflow-layout/scripts/layout_tool.py"

# Store the PAT in a temp file instead of inlining it (then delete it)
printf '%s' '<YOUR_PAT>' > /tmp/jira_tok && chmod 600 /tmp/jira_tok

SRC="https://jira.example.com/secure/admin/workflows/WorkflowDesigner.jspa?wfName=WF_SOURCE&workflowMode=live"
DST="https://jira.example.com/secure/admin/workflows/WorkflowDesigner.jspa?wfName=WF_TARGET&workflowMode=live"

# 1) Back up the TARGET layout first (rollback safety) — always
$TOOL --token-file /tmp/jira_tok backup --url "$DST" --out target_backup.json

# 2) Copy SOURCE layout → TARGET (requires identical step/action IDs)
$TOOL --token-file /tmp/jira_tok copy --from-url "$SRC" --to-url "$DST" --apply

# 3) Auto‑arrange the TARGET into a clean grid (best effort)
$TOOL --token-file /tmp/jira_tok grid --url "$DST" --apply

# 4) Apply a hand‑edited layout body
$TOOL --token-file /tmp/jira_tok apply --url "$DST" --body my_layout.json

rm -f /tmp/jira_tok
```

Notes:
- Without `--apply`, `copy`/`grid` run a **dry‑run**; add `--out file.json` to inspect/edit the body first.
- `live`/`draft` is taken from `workflowMode` in the URL; `--draft` forces the draft.
- URL‑less variant: `--base https://host --name WF` (and `--from/--to` for `copy`).

### Rollback
```bash
$TOOL --token-file /tmp/jira_tok apply --url "$DST" --body target_backup.json
```
(`apply` automatically extracts the `layout` key from a backup file.)

## Fine‑tuning a layout by hand

Generate a body (`grid --out` / `copy --out`), edit the JSON, then `apply --body`:
- `statuses[].x/y` — positions (px; smaller/negative `y` = higher on screen).
- self‑loops — set `sourceAngle`/`targetAngle` (loop bulges toward that direction; spread the
  centers to fan out several self‑loops on the same node).
- connectors — `sourceAngle`/`targetAngle` set the attachment side on each node.

Iterate: apply → reload the Designer → adjust.

## Caveats

- **WebSudo**: some admin endpoints require step‑up auth. If the POST returns `401/403` with an
  `X-Atlassian-WebSudo` header, run the same request from the browser console (already in a
  WebSudo session) or re‑authenticate, then retry.
- **Live vs draft**: `draft:false` writes the active workflow. Layout changes never affect
  execution (positions only).
- **Reload** the Workflow Designer (Ctrl/Cmd+R) after a write to see the result.
- **Internal API**: `/rest/workflowDesigner/...` is undocumented by Atlassian and may change
  between Jira versions — verify after an upgrade. Validated on Jira DC 9.x–10.3.x.

## Security

- The PAT is **never** stored in the skill, the repo, or logs — it is requested at runtime.
- Prefer `--token-file` over `--token`; delete the file after use.
- The tool only changes diagram coordinates; it issues no destructive operations.

## License

MIT — see the repository [`LICENSE`](../LICENSE).

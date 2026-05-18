---
name: memory-management
description: Manage Hermes Agent persistent memory — compress, archive, and maintain memory entries with external detail files.
---

# Memory Management Skill

Manage persistent memory (`memory` and `user` targets) using an **index + external file** pattern to keep token usage low while preserving full detail.

## When to use

- User asks to add/save/remember something
- Memory is getting full (~85%+) and needs compression
- A new project, tool, or preference needs to be recorded
- User corrects you or shares a persistent preference

## The Pattern

**Memory entries** keep short one-line indexes (~30-80 chars).
**Detailed information** goes to `~/.hermes/memory-details/<category>/<topic>.md`.

Each memory entry includes a path reference using **relative paths** under `~/.hermes/memory-details/`:
```
详见 env/server.md      → ~/.hermes/memory-details/env/server.md
详见 projects/eco-demo.md → ~/.hermes/memory-details/projects/eco-demo.md
详见 tools/kanboard.md   → ~/.hermes/memory-details/tools/kanboard.md
```

## Directory Structure

All detail files live under `~/.hermes/memory-details/`:

```
~/.hermes/memory-details/
├── README.md
├── env/           # Server, network, remote access
├── projects/      # Project-specific details
├── accounts/      # Auth, accounts, platform IDs
├── tools/         # Tool configs, API tokens, cron
└── user/          # Preferences, rules, communication style
```

## Workflow

### 1. Adding a new memory

```
Memory entry (short, ~50 chars):
  【tag】Key info. 详见 <relative-path><category>/<file>.md

Detail file (full info):
  ~/.hermes/memory-details/<category>/<file>.md
```

Steps:
1. Determine category (env/projects/accounts/tools/user)
2. Write the detail `.md` file with full info
3. Add a short index entry via `memory(action='add')`

### 2. Editing an existing memory

1. Read the detail file to understand current content
2. Update the detail `.md` file
3. Replace/update the memory entry via `memory(action='replace')`

### 3. Compressing memory when full

When memory reaches ~85%+ usage:

1. Read current entries
2. Identify verbose entries (>80 chars) that can be shortened
3. Write/update detail files in `~/.hermes/memory-details/`
4. Replace verbose entries with compressed index + file path

### 4. Reading detail when needed

When a memory index references a detail file, use `read_file` to load it:
```
read_file(path='~/.hermes/memory-details/projects/eco-demo.md')
```

## Format Convention for Memory Indexes

Use `【tag】` prefix for categorization:
- `【环境】` — server/env/network
- `【项目:xxx】` — projects
- `【规则】` — behavioral rules
- `【新闻】` — news related
- `【工具:xxx】` — tool configs
- `【私密】` — sensitive info
- `【Gitee】/【飞书】` — accounts
- `【股票Agent】/【Crypto】` — agents

## Pitfalls

- DO NOT store secrets/API tokens in memory-details files unless the directory is access-restricted.
- DO NOT put task progress, session outcomes, or temporary state in memory — use `session_search` for that.
- After compressing, verify the `old_text` in `replace()` calls matches unique substrings in existing entries.
- When memory is near full (~95%), remove a low-priority entry first before adding new ones.

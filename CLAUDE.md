# django-design Plugin

Claude Code plugin (v2.0.0) — Production-grade Django development toolkit.

## Structure

- `.claude-plugin/plugin.json` — Plugin manifest
- `skills/django-design/SKILL.md` — Main skill with 11 reference files in `references/`
- `commands/` — 3 interactive commands: django-design, django-app, django-model
- `agents/` — 3 agents: django-architect, django-migrator, django-profiler

## Conventions

- Agent colors must be valid: blue, cyan, green, yellow, magenta, red
- SKILL.md description: ~550 chars max, no keyword-stuffing
- Commands use YAML frontmatter with: description, allowed-tools, argument-hint
- Agents use YAML frontmatter with: name, description (3 examples), model, color, tools
- Reference files contain working code examples with a consistent property-management domain
- Use generic placeholder domains (example.com) in code samples, not real domains

## Development

- `plugin-validator` agent validates structure and naming
- `skill-reviewer` agent checks skill quality and progressive disclosure
- No build step — plugin is pure markdown

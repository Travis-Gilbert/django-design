# django-design Plugin

Claude Code plugin (v3.0.0) — Full-stack Django development toolkit.

## Structure

- `.claude-plugin/plugin.json` — Plugin manifest
- `skills/django-design/SKILL.md` — Main skill with 18 reference files in `references/`
  - Backend: models, views, api, forms, auth-and-security, admin, background-tasks, deployment, performance
  - Frontend: templates, htmx, alpine, tailwind, d3-django, design-system
  - Cross-cutting: testing, integrations, cms-and-content
- `commands/` — 5 interactive commands: django-design, django-app, django-model, django-api, django-component
- `agents/` — 5 agents: django-architect, django-api-reviewer, django-frontend, django-migrator, django-profiler

## Conventions

- Agent colors must be valid: blue, cyan, green, yellow, magenta, red
- SKILL.md description: ~550 chars max, no keyword-stuffing
- Commands use YAML frontmatter with: description, allowed-tools, argument-hint
- Agents use YAML frontmatter with: name, description (3 examples), model, color, tools
- Reference files contain working code examples with a consistent content publishing domain
- Use generic placeholder domains (example.com) in code samples, not real domains

## Development

- `plugin-validator` agent validates structure and naming
- `skill-reviewer` agent checks skill quality and progressive disclosure
- No build step — plugin is pure markdown

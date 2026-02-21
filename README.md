# django-design

Production-grade Django development toolkit for Claude Code. Provides architecture guidance, interactive project scaffolding, and proactive code review with auto-fix.

## Components

### Skill: django-design

Activates automatically when working on Django projects. Covers:

- Project structure (settings package, apps directory, fat models / thin views)
- Model design (field types, indexes, managers, constraints)
- View patterns (FBV vs CBV, DRF, pagination, select_related)
- Authentication (built-in, Clerk/Auth0, token-based)
- Admin customization (django-unfold, fieldsets, actions)
- Deployment (Railway, Docker, Gunicorn, static files)
- Testing (factory_boy, pytest-django, query performance)

Reference files in `skills/django-design/references/` provide deep dives on each topic.

### Command: /django-design

Interactive project scaffold. Asks about project name, domain, scale, auth approach, API style, deployment target, and database — then generates a complete Django project with:

- Settings split into `base.py` / `development.py` / `production.py`
- Apps directory with `core` app and `TimeStampedModel` base
- Custom `User` model (always, even if not using auth yet)
- Requirements files per environment
- Security settings pre-configured for production
- `.env.example` and `.gitignore`

Usage: Type `/django-design` in Claude Code and follow the prompts.

### Agent: django-architect

Architecture reviewer that triggers:

- **Proactively** after writing significant Django code (models, views, settings, admin)
- **Reactively** when asked to review Django code

Checks for missing indexes, N+1 query risks, security issues, fat-view anti-patterns, and more. Fixes Critical and Warning issues automatically; asks before fixing Info-level items.

## Installation

Already installed as a local plugin. To reinstall or share:

1. Copy the `django-design/` directory to `~/.claude/plugins/marketplaces/local-desktop-app-uploads/`
2. Restart Claude Code

## File Structure

```
django-design/
├── .claude-plugin/
│   └── plugin.json
├── commands/
│   └── django-design.md
├── agents/
│   └── django-architect.md
└── skills/
    └── django-design/
        ├── SKILL.md
        └── references/
            ├── models.md
            ├── views.md
            ├── auth-and-security.md
            ├── deployment.md
            ├── admin.md
            ├── integrations.md
            └── testing.md
```

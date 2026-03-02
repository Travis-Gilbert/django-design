#!/bin/bash
# organize.sh -- restructure for Claude Code

DIR="$(cd "$(dirname "$0")" && pwd)"

# 1. Move agents into agents/
mkdir -p "$DIR/agents"
for f in "$DIR"/*-developer.md "$DIR"/*-engineer.md "$DIR"/*-pro.md \
         "$DIR"/*-specialist.md "$DIR"/*-designer.md "$DIR"/*-modernizer.md; do
  [ -f "$f" ] && mv "$f" "$DIR/agents/"
done

# 2. Move repos into refs/
mkdir -p "$DIR/refs"
for d in alpine-main d3-main django-cotton-main django-rest-framework-main \
         Django-Ninja django-imagekit-develop django-unicorn-main \
         django-tailwind-cli-main django-tailwind-master htmx-master \
         "HTMX master" plot-main framework-main "Rest framework" \
         "Alpine references" "django-smartbas"*; do
  [ -d "$DIR/$d" ] && mv "$DIR/$d" "$DIR/refs/"
done

# 3. Move Cotton internals into the Cotton ref
mkdir -p "$DIR/refs/django-cotton-main/src-loose"
for f in _component.py _slot.py "_slot copy.py" _vars.py cotton.py \
         cotton_loader.py tag_parser.py compiler_regex.py \
         nested_tag_support.py; do
  [ -f "$DIR/$f" ] && mv "$DIR/$f" "$DIR/refs/django-cotton-main/src-loose/"
done

# 4. Move HTML examples
mkdir -p "$DIR/examples/html-references"
for f in "$DIR"/*.html; do
  [ -f "$f" ] && mv "$f" "$DIR/examples/html-references/"
done

# 5. Move test/settings files
mkdir -p "$DIR/examples/config-references"
for f in settings.py "settings 2.py" test_settings.py apps.py; do
  [ -f "$DIR/$f" ] && mv "$DIR/$f" "$DIR/examples/config-references/"
done

# 6. Consolidate template folders
mkdir -p "$DIR/examples/template-references"
for d in templates "templates 2" "templates 3" "templates 4"; do
  [ -d "$DIR/$d" ] && mv "$DIR/$d" "$DIR/examples/template-references/"
done

# 7. Remove copy/duplicate files (review first)
echo "Review these for deletion:"
ls "$DIR"/*copy* "$DIR"/*" 2"* 2>/dev/null

# 8. Clone missing critical repos
echo "Cloning missing repos..."
[ ! -d "$DIR/refs/django-main" ] && \
  git clone --depth 1 https://github.com/django/django.git "$DIR/refs/django-main"
[ ! -d "$DIR/refs/celery-main" ] && \
  git clone --depth 1 https://github.com/celery/celery.git "$DIR/refs/celery-main"
[ ! -d "$DIR/refs/django-htmx-main" ] && \
  git clone --depth 1 https://github.com/adamchainz/django-htmx.git "$DIR/refs/django-htmx-main"
[ ! -d "$DIR/refs/django-filter-main" ] && \
  git clone --depth 1 https://github.com/carltongibson/django-filter.git "$DIR/refs/django-filter-main"
[ ! -d "$DIR/refs/django-template-partials-main" ] && \
  git clone --depth 1 https://github.com/carltongibson/django-template-partials.git \
  "$DIR/refs/django-template-partials-main"

echo "Done. Now create CLAUDE.md at the root."
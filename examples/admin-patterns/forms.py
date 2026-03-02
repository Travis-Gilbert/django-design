"""
Admin form customization patterns for a content publishing site.

Demonstrates:
- Custom ModelForm for admin with clean methods
- Widget overrides (AdminTextareaWidget, AdminDateWidget)
- Conditional field requirements based on status
- Field-level and cross-field validation
- Help text overrides for admin context

Domain: content publishing site with Essay and FieldNote models.
"""
from django import forms
from django.contrib.admin.widgets import (
    AdminDateWidget,
    AdminTextareaWidget,
    AutocompleteSelect,
    AutocompleteSelectMultiple,
)
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from .models import Essay, FieldNote


class EssayAdminForm(forms.ModelForm):
    """
    Custom form for Essay admin with business-rule validation.

    Key patterns:
    - Widget overrides make certain fields more usable in admin context.
    - clean() enforces rules that depend on the essay's stage: published
      essays must have an excerpt, body, and at least one tag.
    - Individual clean_<field> methods handle field-specific validation.

    The form is referenced by EssayAdmin.form so it replaces the
    auto-generated ModelForm.
    """

    class Meta:
        model = Essay
        fields = "__all__"
        widgets = {
            # Use the larger textarea widget for body content.
            # The default TextInput is too small for long-form writing.
            "body": AdminTextareaWidget(attrs={
                "rows": 30,
                "cols": 100,
                "style": "font-family: monospace; font-size: 14px;",
            }),
            "excerpt": AdminTextareaWidget(attrs={
                "rows": 4,
                "cols": 100,
            }),
            "meta_description": AdminTextareaWidget(attrs={
                "rows": 3,
                "cols": 80,
            }),
        }
        help_texts = {
            "title": "The display title. Keep it under 100 characters for SEO.",
            "slug": "URL-safe identifier. Auto-populated from title.",
            "excerpt": (
                "Short summary shown on listing pages and in social cards. "
                "Required when publishing."
            ),
            "meta_title": (
                "Override the default <title> tag. "
                "Leave blank to use the essay title."
            ),
            "meta_description": (
                "Description for search engines. 150-160 characters is ideal."
            ),
            "body": "Full essay content. Markdown is supported.",
        }

    def clean_title(self):
        """
        Validate the title.

        - Strip leading/trailing whitespace.
        - Enforce a maximum length suitable for SEO titles.
        - Check that the generated slug would not be empty.
        """
        title = self.cleaned_data.get("title", "").strip()
        if not title:
            raise ValidationError("Title cannot be blank.")
        if len(title) > 200:
            raise ValidationError(
                "Title must be 200 characters or fewer. "
                f"Current length: {len(title)}."
            )
        # Ensure the title produces a usable slug
        candidate_slug = slugify(title)
        if not candidate_slug:
            raise ValidationError(
                "Title must contain at least one alphanumeric character "
                "so a valid slug can be generated."
            )
        return title

    def clean_meta_description(self):
        """Warn (not error) if meta description is outside the ideal range."""
        desc = self.cleaned_data.get("meta_description", "")
        if desc and len(desc) > 160:
            raise ValidationError(
                "Meta description should be 160 characters or fewer for "
                f"best SEO results. Current length: {len(desc)}."
            )
        return desc

    def clean_excerpt(self):
        """Strip whitespace from excerpt."""
        return (self.cleaned_data.get("excerpt") or "").strip()

    def clean(self):
        """
        Cross-field validation based on publication stage.

        When stage is "published", certain fields become required even
        though the model allows them to be blank. This enforces editorial
        standards without making every draft fill in all metadata.

        Pattern: conditional requirements based on a status field.
        """
        cleaned = super().clean()
        stage = cleaned.get("stage")

        if stage == "published":
            errors = {}

            # Published essays must have body content
            body = cleaned.get("body", "")
            if not body or not body.strip():
                errors["body"] = ValidationError(
                    "Published essays must have body content.",
                    code="required_for_publish",
                )

            # Published essays must have an excerpt for listing pages
            excerpt = cleaned.get("excerpt", "")
            if not excerpt:
                errors["excerpt"] = ValidationError(
                    "Published essays must have an excerpt for listing pages.",
                    code="required_for_publish",
                )

            # Published essays should have at least one tag
            tags = cleaned.get("tags")
            if tags is not None and not tags:
                errors["tags"] = ValidationError(
                    "Published essays must have at least one tag.",
                    code="required_for_publish",
                )

            if errors:
                raise ValidationError(errors)

        if stage == "production":
            # Production stage requires body content but not excerpt
            body = cleaned.get("body", "")
            if not body or not body.strip():
                raise ValidationError({
                    "body": ValidationError(
                        "Essays in production must have body content.",
                        code="required_for_production",
                    ),
                })

        return cleaned


class FieldNoteAdminForm(forms.ModelForm):
    """
    Custom form for FieldNote admin.

    Simpler than EssayAdminForm because field notes have fewer editorial
    requirements. Demonstrates widget overrides and basic validation.
    """

    class Meta:
        model = FieldNote
        fields = "__all__"
        widgets = {
            "body": AdminTextareaWidget(attrs={
                "rows": 15,
                "cols": 100,
            }),
        }
        help_texts = {
            "title": "Brief descriptive title for this field note.",
            "body": "The note content. Keep it focused and concise.",
        }

    def clean_title(self):
        """Strip whitespace and enforce minimum length."""
        title = self.cleaned_data.get("title", "").strip()
        if len(title) < 3:
            raise ValidationError(
                "Field note title must be at least 3 characters."
            )
        return title

    def clean(self):
        """Field notes require body content regardless of stage."""
        cleaned = super().clean()
        body = cleaned.get("body", "")
        if not body or not body.strip():
            raise ValidationError({
                "body": "Field notes must have body content."
            })
        return cleaned


# ---------------------------------------------------------------------------
# Reusable form mixin patterns
# ---------------------------------------------------------------------------

class SlugValidationMixin:
    """
    Mixin for admin forms that include a slug field.

    Validates that the slug is URL-safe and checks uniqueness against the
    model's table. Include this in your form's bases alongside ModelForm.

    Usage:
        class MyAdminForm(SlugValidationMixin, forms.ModelForm):
            class Meta:
                model = MyModel
                fields = "__all__"
    """

    def clean_slug(self):
        slug = self.cleaned_data.get("slug", "")
        if slug != slugify(slug):
            raise ValidationError(
                "Slug must contain only lowercase letters, numbers, and hyphens."
            )

        # Check uniqueness, excluding the current instance
        model = self._meta.model
        qs = model.objects.filter(slug=slug)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(
                f"A {model._meta.verbose_name} with this slug already exists."
            )
        return slug


class StageTransitionMixin:
    """
    Mixin that validates allowed stage transitions.

    Prevents editors from skipping stages (e.g., going directly from
    "research" to "published" without passing through "drafting" and
    "production").

    Usage:
        ALLOWED_TRANSITIONS = {
            "research": {"research", "drafting"},
            "drafting": {"drafting", "production", "research"},
            "production": {"production", "published", "drafting"},
            "published": {"published", "production"},
        }

        class MyAdminForm(StageTransitionMixin, forms.ModelForm):
            ALLOWED_TRANSITIONS = ALLOWED_TRANSITIONS
            ...
    """
    ALLOWED_TRANSITIONS = {}

    def clean_stage(self):
        new_stage = self.cleaned_data.get("stage")
        if not self.instance or not self.instance.pk:
            return new_stage

        old_stage = type(self.instance).objects.filter(
            pk=self.instance.pk
        ).values_list("stage", flat=True).first()

        if old_stage and old_stage in self.ALLOWED_TRANSITIONS:
            allowed = self.ALLOWED_TRANSITIONS[old_stage]
            if new_stage not in allowed:
                allowed_display = ", ".join(sorted(allowed))
                raise ValidationError(
                    f"Cannot transition from '{old_stage}' to '{new_stage}'. "
                    f"Allowed transitions: {allowed_display}."
                )
        return new_stage

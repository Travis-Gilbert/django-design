# Django Forms Reference

## Forms Architecture

Django forms are the bridge between user input and validated data. They handle rendering, validation, and cleaning in a single abstraction. The key is knowing when to use each form type and how to keep form logic from leaking into views.

### ModelForm Patterns

ModelForm is the default choice when a form maps directly to a model. Let the model do the heavy lifting.

```python
from django import forms
from apps.content.models import Essay


class EssayForm(forms.ModelForm):
    class Meta:
        model = Essay
        fields = [
            'title', 'slug', 'date', 'stage',
            'summary', 'body', 'tags', 'draft',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'title': forms.TextInput(attrs={'placeholder': 'Essay title'}),
            'summary': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {
            'slug': 'URL-friendly identifier. Must be unique.',
        }

    def clean_slug(self):
        """Field-level validation. Runs after the field's built-in validation."""
        slug = self.cleaned_data['slug']
        if Essay.objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('An essay with this slug already exists.')
        return slug

    def clean(self):
        """Cross-field validation. Runs after all field-level clean methods."""
        cleaned_data = super().clean()
        stage = cleaned_data.get('stage')
        summary = cleaned_data.get('summary')

        if stage == 'published' and not summary:
            self.add_error(
                'summary',
                'Published essays require a summary.',
            )
        return cleaned_data
```

**When to use ModelForm vs plain Form:**
- `ModelForm`: When the form maps to a model and you want automatic field generation, validation, and `save()`.
- `Form`: When the form does not map to a single model (search forms, multi-model wizards, contact forms), or when you need full control over every field.

### Plain Form Example

```python
class EssaySearchForm(forms.Form):
    """Search form with no model backing. Used for filtering essay lists."""
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Search by title or slug'}),
    )
    stage = forms.ChoiceField(
        required=False,
        choices=[('', 'All Stages')] + Essay.Stage.choices,
    )
    tag = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Filter by tag'}),
    )
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        if date_from and date_to and date_from > date_to:
            self.add_error('date_to', 'End date must be after start date.')
        return cleaned_data

    def filter_queryset(self, qs):
        """Apply form values to a queryset. Keeps filtering logic on the form, not the view."""
        if self.cleaned_data.get('q'):
            qs = qs.filter(
                Q(title__icontains=self.cleaned_data['q'])
                | Q(slug__icontains=self.cleaned_data['q'])
            )
        if self.cleaned_data.get('stage'):
            qs = qs.filter(stage=self.cleaned_data['stage'])
        if self.cleaned_data.get('tag'):
            qs = qs.filter(tags__contains=[self.cleaned_data['tag']])
        if self.cleaned_data.get('date_from'):
            qs = qs.filter(date__gte=self.cleaned_data['date_from'])
        if self.cleaned_data.get('date_to'):
            qs = qs.filter(date__lte=self.cleaned_data['date_to'])
        return qs
```

### Formsets

Formsets handle multiple instances of the same form on one page. Inline formsets tie child forms to a parent object.

```python
from django.forms import inlineformset_factory
from apps.content.models import VideoProject, VideoScene

SceneFormSet = inlineformset_factory(
    VideoProject,
    VideoScene,
    fields=['title', 'scene_type', 'script_text', 'order'],
    extra=1,          # one blank form for adding new scenes
    can_delete=True,   # allow removing existing scenes
    max_num=50,        # cap the total number
)


# In the view
def video_edit(request, slug):
    video = get_object_or_404(VideoProject, slug=slug)

    if request.method == 'POST':
        form = VideoProjectForm(request.POST, instance=video)
        formset = SceneFormSet(request.POST, instance=video)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect('content:video-detail', slug=video.slug)
    else:
        form = VideoProjectForm(instance=video)
        formset = SceneFormSet(instance=video)

    return render(request, 'content/video_edit.html', {
        'form': form,
        'scene_formset': formset,
    })
```

### Custom Widgets

Widgets control how a field renders. Override them for richer UI without changing validation.

```python
class ColorPickerWidget(forms.TextInput):
    template_name = 'widgets/color_picker.html'

    class Media:
        css = {'all': ('css/color-picker.css',)}
        js = ('js/color-picker.js',)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['swatches'] = ['#FF5733', '#33FF57', '#3357FF']
        return context


class AutocompleteWidget(forms.Select):
    """Select widget with server-side search. Works with HTMX or Unpoly."""
    template_name = 'widgets/autocomplete.html'

    def __init__(self, search_url, *args, **kwargs):
        self.search_url = search_url
        super().__init__(*args, **kwargs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['search_url'] = self.search_url
        return context
```

### Form Rendering Control

Django 5+ supports custom form renderers. Use them to globally control how forms render across the project.

```python
# settings/base.py
FORM_RENDERER = 'django.forms.renderers.TemplatesSetting'

# This tells Django to look in your templates/ directory for form templates.
# Override individual field templates:
# templates/django/forms/widgets/input.html
# templates/django/forms/widgets/select.html
```

For per-form rendering control in templates (see templates.md for full template patterns):

```html
{# Render fields individually for maximum control #}
{% for field in form %}
<div class="form-field {% if field.errors %}has-error{% endif %}">
    <label for="{{ field.id_for_label }}">{{ field.label }}</label>
    {{ field }}
    {% if field.help_text %}
        <span class="help-text">{{ field.help_text }}</span>
    {% endif %}
    {% for error in field.errors %}
        <span class="error-message">{{ error }}</span>
    {% endfor %}
</div>
{% endfor %}
```

### Form Validation Order

Understanding the validation chain prevents debugging surprises:

1. **`field.clean()`** - Built-in field validation (type checking, max_length, etc.)
2. **`clean_<fieldname>()`** - Your per-field custom validation
3. **`clean()`** - Cross-field validation (comparing two fields, conditional rules)
4. **`validate_unique()`** - Model-level uniqueness (ModelForm only)

Each step only runs if previous steps passed. If `clean_slug()` raises `ValidationError`, `clean()` still runs but `cleaned_data` will not contain `slug`.

## Anti-Patterns

- **Duplicating validation in templates.** If the form validates `max_length=100`, do not also add a `maxlength="100"` attribute manually. Use `{{ form.field }}` and let Django handle it.
- **Ignoring form media.** If a widget defines `class Media`, use `{{ form.media }}` in the template head. Forgetting this is why custom widgets "don't work."
- **Validation in views.** If you find yourself writing `if request.POST.get('stage') and request.POST['stage'] not in valid_stages` in a view, that logic belongs on the form.
- **Skipping `form.is_valid()`.** Never access `cleaned_data` without calling `is_valid()` first. It will either not exist or contain unvalidated data.

"""
DRF Serializer Patterns
=======================

Reference patterns for Django REST Framework serializers using the content
publishing domain (Essay, Tag, FieldNote, etc.).

Patterns covered:
    - ModelSerializer with field selection and read_only_fields
    - Nested serializers (read and write)
    - WritableNestedSerializer for creating/updating related objects
    - SerializerMethodField for computed fields
    - Field-level and object-level validation
    - SlugRelatedField for M2M
    - Custom create() and update()
    - Serializer inheritance
    - to_representation override for conditional fields

All examples assume models are defined in apps/content/models.py.
See the content-publishing-site example for the full model definitions.
"""

from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers

from apps.content.models import (
    Essay,
    EssayRevision,
    FieldNote,
    Project,
    Tag,
)


# ---------------------------------------------------------------------------
# 1. Basic ModelSerializer with field selection
# ---------------------------------------------------------------------------

class TagSerializer(serializers.ModelSerializer):
    """
    Straightforward ModelSerializer.

    Key points:
    - Explicit field list (never use '__all__' in production).
    - read_only_fields for auto-generated values.
    - extra_kwargs for field-level overrides without redefining the field.
    """

    class Meta:
        model = Tag
        fields = ["id", "name", "slug", "usage_count"]
        read_only_fields = ["id", "slug", "usage_count"]
        extra_kwargs = {
            "name": {"min_length": 2, "max_length": 50},
        }


# ---------------------------------------------------------------------------
# 2. Nested read-only serializer with SerializerMethodField
# ---------------------------------------------------------------------------

class EssayListSerializer(serializers.ModelSerializer):
    """
    List serializer -- lighter than the detail serializer.

    Key points:
    - Separate list/detail serializers to avoid over-fetching.
    - Nested TagSerializer is read-only here; write uses SlugRelatedField.
    - SerializerMethodField for values computed from the instance.
    - source kwarg to map a serializer field to a different model field.
    """

    author_name = serializers.CharField(source="author.get_full_name", read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    word_count = serializers.SerializerMethodField()
    reading_time_minutes = serializers.SerializerMethodField()

    class Meta:
        model = Essay
        fields = [
            "id",
            "title",
            "slug",
            "author_name",
            "stage",
            "tags",
            "word_count",
            "reading_time_minutes",
            "published_at",
            "created_at",
        ]
        read_only_fields = ["id", "slug", "published_at", "created_at"]

    def get_word_count(self, obj: Essay) -> int:
        """Compute word count from the body text."""
        if not obj.body:
            return 0
        return len(obj.body.split())

    def get_reading_time_minutes(self, obj: Essay) -> int:
        """Estimate reading time at ~200 words per minute."""
        word_count = self.get_word_count(obj)
        return max(1, round(word_count / 200))


# ---------------------------------------------------------------------------
# 3. Detail serializer with SlugRelatedField for writable M2M
# ---------------------------------------------------------------------------

class EssayDetailSerializer(EssayListSerializer):
    """
    Detail serializer -- inherits list fields, adds body and writable tags.

    Key points:
    - Serializer inheritance: reuse EssayListSerializer, extend fields.
    - SlugRelatedField lets the client send tag names instead of PKs.
    - many=True on SlugRelatedField for M2M relationships.
    - The queryset argument is required for writable related fields.
    """

    tags = serializers.SlugRelatedField(
        many=True,
        slug_field="name",
        queryset=Tag.objects.all(),
    )

    class Meta(EssayListSerializer.Meta):
        fields = EssayListSerializer.Meta.fields + ["body", "summary"]

    # -- Field-level validation ------------------------------------------

    def validate_title(self, value: str) -> str:
        """
        Field-level validation runs before object-level validate().

        DRF calls validate_<field_name> for each field, then calls
        validate() with the full dict. Use field-level for single-field
        rules and object-level for cross-field rules.
        """
        if value and value[0].islower():
            raise serializers.ValidationError(
                "Title must start with an uppercase letter."
            )
        return value

    # -- Object-level validation -----------------------------------------

    def validate(self, attrs: dict) -> dict:
        """
        Cross-field validation.

        This runs after all field-level validators have passed.
        Access validated data through `attrs`, not `self.initial_data`.
        """
        stage = attrs.get("stage", getattr(self.instance, "stage", None))
        body = attrs.get("body", getattr(self.instance, "body", None))

        if stage == "published" and not body:
            raise serializers.ValidationError(
                {"body": "Body is required before publishing."}
            )

        if stage == "published" and not attrs.get(
            "summary", getattr(self.instance, "summary", None)
        ):
            raise serializers.ValidationError(
                {"summary": "Summary is required before publishing."}
            )

        return attrs

    # -- Custom create ---------------------------------------------------

    def create(self, validated_data: dict) -> Essay:
        """
        Custom create for handling M2M (tags).

        M2M fields cannot be set until the instance has a PK, so:
        1. Pop M2M data before creating the instance.
        2. Create the instance.
        3. Set M2M relationships.
        """
        tags = validated_data.pop("tags", [])
        essay = Essay.objects.create(**validated_data)
        essay.tags.set(tags)
        return essay

    def update(self, instance: Essay, validated_data: dict) -> Essay:
        """
        Custom update mirroring the create pattern for M2M.
        """
        tags = validated_data.pop("tags", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if tags is not None:
            instance.tags.set(tags)

        return instance


# ---------------------------------------------------------------------------
# 4. WritableNestedSerializer pattern
# ---------------------------------------------------------------------------

class EssayRevisionSerializer(serializers.ModelSerializer):
    """Serializer for a single revision of an essay."""

    class Meta:
        model = EssayRevision
        fields = ["id", "revision_number", "body_snapshot", "notes", "created_at"]
        read_only_fields = ["id", "revision_number", "created_at"]


class EssayWithRevisionsSerializer(serializers.ModelSerializer):
    """
    Writable nested serializer -- creating child objects alongside parent.

    Key points:
    - DRF does NOT handle nested writes automatically. You must override
      create() and update() to handle child objects.
    - Pop nested data before calling super() or Model.objects.create().
    - Decide whether nested objects are created, replaced, or patched on
      update. This example replaces all revisions on update.

    Verify this pattern against the actual DRF source:
        refs/django-rest-framework-main/rest_framework/serializers.py
        Search for: "raise_errors_on_nested_writes"
    """

    revisions = EssayRevisionSerializer(many=True, required=False)
    tags = serializers.SlugRelatedField(
        many=True,
        slug_field="name",
        queryset=Tag.objects.all(),
    )

    class Meta:
        model = Essay
        fields = [
            "id",
            "title",
            "slug",
            "body",
            "stage",
            "tags",
            "revisions",
            "created_at",
        ]
        read_only_fields = ["id", "slug", "created_at"]

    def create(self, validated_data: dict) -> Essay:
        revisions_data = validated_data.pop("revisions", [])
        tags = validated_data.pop("tags", [])

        essay = Essay.objects.create(**validated_data)
        essay.tags.set(tags)

        for idx, revision_data in enumerate(revisions_data, start=1):
            EssayRevision.objects.create(
                essay=essay,
                revision_number=idx,
                **revision_data,
            )

        return essay

    def update(self, instance: Essay, validated_data: dict) -> Essay:
        revisions_data = validated_data.pop("revisions", None)
        tags = validated_data.pop("tags", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if tags is not None:
            instance.tags.set(tags)

        if revisions_data is not None:
            # Strategy: replace all revisions. Other strategies include
            # partial update (match by id) or append-only.
            instance.revisions.all().delete()
            for idx, revision_data in enumerate(revisions_data, start=1):
                EssayRevision.objects.create(
                    essay=instance,
                    revision_number=idx,
                    **revision_data,
                )

        return instance


# ---------------------------------------------------------------------------
# 5. to_representation override for conditional fields
# ---------------------------------------------------------------------------

class EssayPublicSerializer(serializers.ModelSerializer):
    """
    Serializer that conditionally includes fields in the response.

    Key points:
    - to_representation() runs after serialization and lets you modify
      the output dict.
    - Use this for conditional fields, field renaming, or format changes
      that do not affect validation/deserialization.
    - Avoid heavy computation here; it runs per-object.
    """

    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = Essay
        fields = [
            "id",
            "title",
            "slug",
            "body",
            "summary",
            "stage",
            "tags",
            "published_at",
        ]

    def to_representation(self, instance: Essay) -> dict:
        data = super().to_representation(instance)

        # Hide the full body for unpublished essays in public responses.
        if instance.stage != "published":
            data.pop("body", None)

        # Add a convenience URL field.
        request = self.context.get("request")
        if request:
            data["url"] = request.build_absolute_uri(
                f"/essays/{instance.slug}/"
            )

        return data


# ---------------------------------------------------------------------------
# 6. FieldNote serializer -- standalone example with auto-slug
# ---------------------------------------------------------------------------

class FieldNoteSerializer(serializers.ModelSerializer):
    """
    Simpler serializer showing auto-slug generation in create().

    Key points:
    - Slug is generated server-side, so it is read-only on the serializer.
    - author is set from the request in the viewset's perform_create(),
      not in the serializer. Keep the serializer free of request awareness
      when possible.
    """

    author_name = serializers.CharField(source="author.get_full_name", read_only=True)

    class Meta:
        model = FieldNote
        fields = [
            "id",
            "title",
            "slug",
            "body",
            "author",
            "author_name",
            "tags",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "author", "created_at", "updated_at"]

    def create(self, validated_data: dict) -> FieldNote:
        validated_data["slug"] = slugify(validated_data["title"])
        return super().create(validated_data)


# ---------------------------------------------------------------------------
# 7. Project serializer -- cross-service slug reference
# ---------------------------------------------------------------------------

class ProjectSerializer(serializers.ModelSerializer):
    """
    Cross-service reference using slug strings instead of ForeignKeys.

    The content publishing site and research API are separate Django services.
    They reference each other by slug, not by database FK. This serializer
    accepts a list of research thread slugs as plain strings.

    Key points:
    - CharField with many=True does not exist; use ListField + CharField.
    - Validate that referenced slugs follow the expected format.
    - The actual existence check happens in the service layer, not here,
      because the referenced objects live in a different database.
    """

    research_thread_slugs = serializers.ListField(
        child=serializers.SlugField(max_length=100),
        required=False,
        allow_empty=True,
        help_text="Slugs referencing research threads in the Research API.",
    )

    class Meta:
        model = Project
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "stage",
            "research_thread_slugs",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

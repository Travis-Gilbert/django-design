"""
DRF Permission Patterns
=======================

Reference patterns for Django REST Framework custom permissions using the
content publishing domain.

Patterns covered:
    - Custom IsAuthorOrReadOnly permission
    - Object-level permission with has_object_permission
    - Combining permissions with AND/OR logic
    - Role-based permission
    - Stage-based permission (domain-specific)

Verify against the actual DRF permission implementation:
    refs/django-rest-framework-main/rest_framework/permissions.py
"""

from rest_framework import permissions


# ---------------------------------------------------------------------------
# 1. IsAuthorOrReadOnly -- the classic object-level permission
# ---------------------------------------------------------------------------

class IsAuthorOrReadOnly(permissions.BasePermission):
    """
    Allow full access to the author of an object; read-only for everyone else.

    Key points:
    - has_permission() gates the entire view (called first on every request).
    - has_object_permission() gates individual objects (called by
      get_object(), which means it runs for detail views and custom actions
      but NOT for list views).
    - Safe methods: GET, HEAD, OPTIONS.
    - The object must have an `author` attribute. Adjust the field name
      to match your model (e.g., `owner`, `created_by`).
    """

    def has_permission(self, request, view):
        # Allow all authenticated users to list/create.
        # has_object_permission handles per-object checks.
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Read permissions for any request.
        if request.method in permissions.SAFE_METHODS:
            return True
        # Write permissions only for the author.
        return obj.author == request.user


# ---------------------------------------------------------------------------
# 2. IsEditorOrReadOnly -- role-based permission
# ---------------------------------------------------------------------------

class IsEditorOrReadOnly(permissions.BasePermission):
    """
    Users in the 'editors' group get write access; others get read-only.

    Key points:
    - Role checks via Django's Group model.
    - has_permission() is enough here because the check is not per-object.
    - Cache the group membership check if it becomes a performance concern.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.groups.filter(name="editors").exists()


# ---------------------------------------------------------------------------
# 3. CanPublish -- domain-specific permission
# ---------------------------------------------------------------------------

class CanPublish(permissions.BasePermission):
    """
    Only users with the 'content.can_publish' permission may set an essay's
    stage to 'published'.

    Key points:
    - Reads request.data to check the intended action, not just the HTTP method.
    - This is a view-level permission, not object-level, because it gates
      the entire action (publish) rather than a specific object attribute.
    - The corresponding model permission is defined in the Essay model's Meta:
          permissions = [("can_publish", "Can publish essays")]
    """

    def has_permission(self, request, view):
        # Only restrict requests that attempt to set stage=published.
        if request.method in permissions.SAFE_METHODS:
            return True

        new_stage = request.data.get("stage")
        if new_stage != "published":
            return True

        return request.user.has_perm("content.can_publish")


# ---------------------------------------------------------------------------
# 4. IsAdminOrAuthorForDestructive -- combining logic in one class
# ---------------------------------------------------------------------------

class IsAdminOrAuthorForDestructive(permissions.BasePermission):
    """
    DELETE requires admin or author. Other writes require author only.

    Key points:
    - You can handle complex logic in a single permission class by
      branching on request.method inside has_object_permission.
    - Alternatively, compose simpler permissions with & and | operators
      (shown below in the usage examples).
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        if request.method == "DELETE":
            return request.user.is_staff or obj.author == request.user

        return obj.author == request.user


# ---------------------------------------------------------------------------
# 5. ReadOnly -- utility permission for composition
# ---------------------------------------------------------------------------

class ReadOnly(permissions.BasePermission):
    """
    Only allow safe (read-only) methods.

    Useful as a building block for permission composition with | and &.
    """

    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS


# ---------------------------------------------------------------------------
# 6. Permission composition examples (for use in ViewSet classes)
# ---------------------------------------------------------------------------

# DRF supports composing permission classes with bitwise operators:
#
#   permission_classes = [IsAuthenticated & IsAuthorOrReadOnly]
#       -> Both must pass (AND logic). This is the default when you list
#          multiple classes: [IsAuthenticated, IsAuthorOrReadOnly] also
#          requires both to pass.
#
#   permission_classes = [IsAdminUser | IsAuthorOrReadOnly]
#       -> Either can pass (OR logic). Useful when multiple roles should
#          have access through different criteria.
#
#   permission_classes = [IsAuthenticated & (IsEditorOrReadOnly | IsAuthorOrReadOnly)]
#       -> Must be authenticated AND (either an editor or the author).
#
# The composed permission is itself a permission class, so it works
# everywhere a single class does.
#
# Example in a ViewSet:
#
#   class EssayViewSet(viewsets.ModelViewSet):
#       def get_permissions(self):
#           if self.action == "destroy":
#               return [(permissions.IsAdminUser | IsAuthorOrReadOnly)()]
#           if self.action in ("update", "partial_update"):
#               return [IsAuthorOrReadOnly()]
#           return [permissions.IsAuthenticatedOrReadOnly()]
#
# Note: When using | operator, wrap in parentheses and instantiate the
# result -- DRF expects a list of permission *instances*, not classes,
# when returned from get_permissions().

# Authentication, Permissions, and Security Reference

## Authentication Options

### Django's Built-in Auth
Good for: traditional server-rendered apps, admin-heavy applications, internal tools.

```python
# settings/base.py
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

AUTH_USER_MODEL = 'core.User'  # always set this, even if you start with the default


# apps/core/models.py
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Custom user model. Always define this at project start,
    even if you don't need extra fields yet. Changing the user
    model after migrations exist is painful."""
    
    organization = models.ForeignKey(
        'Organization', on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    role = models.CharField(
        max_length=30,
        choices=UserRole.choices,
        default=UserRole.VIEWER,
    )
    
    class Meta:
        indexes = [
            models.Index(fields=['organization', 'role']),
        ]
```

**Always define a custom user model at the start.** Even if `AbstractUser` with zero extra fields. Migrating later is one of Django's most painful operations.

### DRF Token Authentication
Good for: simple API-only applications, mobile app backends.

```python
# settings/base.py
INSTALLED_APPS = [
    ...
    'rest_framework.authtoken',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',  # for browsable API
    ],
}
```

### External Auth Providers (Clerk, Auth0, etc.)
Good for: applications that need to offload user management, SSO, or social login.

```python
# Integration pattern for Clerk or similar JWT-based providers

# apps/core/authentication.py
import jwt
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class ClerkAuthentication(BaseAuthentication):
    """Validate Clerk JWT tokens and map to Django users."""
    
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header[7:]
        
        try:
            payload = jwt.decode(
                token,
                settings.CLERK_PUBLIC_KEY,
                algorithms=['RS256'],
                audience=settings.CLERK_AUDIENCE,
            )
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError:
            raise AuthenticationFailed('Invalid token')
        
        user = self._get_or_create_user(payload)
        return (user, payload)
    
    def _get_or_create_user(self, payload):
        """Map Clerk user to Django user, creating if needed."""
        from apps.core.models import User
        
        clerk_id = payload.get('sub')
        email = payload.get('email', '')
        
        user, created = User.objects.get_or_create(
            clerk_id=clerk_id,
            defaults={
                'email': email,
                'username': email or clerk_id,
            },
        )
        
        if not created and user.email != email:
            user.email = email
            user.save(update_fields=['email'])
        
        return user
```

## Permission Architecture

### Model-Level Permissions
Django auto-creates add/change/delete/view permissions for every model. Use them.

```python
from django.contrib.auth.decorators import permission_required
from rest_framework.permissions import DjangoModelPermissions


# Function-based view
@permission_required('properties.change_property', raise_exception=True)
def update_property(request, property_id):
    ...


# DRF: DjangoModelPermissions maps HTTP methods to model permissions automatically
class PropertyViewSet(viewsets.ModelViewSet):
    permission_classes = [DjangoModelPermissions]
```

### Custom Permissions
For business rules that go beyond CRUD.

```python
from rest_framework.permissions import BasePermission


class CanApproveCompliance(BasePermission):
    """Only compliance officers and managers can approve."""
    
    def has_permission(self, request, view):
        return request.user.role in ['compliance_officer', 'manager', 'admin']


class IsPropertyAssignee(BasePermission):
    """Users can only modify properties assigned to them,
    unless they're a manager or admin."""
    
    def has_object_permission(self, request, view, obj):
        if request.user.role in ['manager', 'admin']:
            return True
        return obj.assigned_to == request.user


class PropertyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        if self.action == 'approve':
            return [CanApproveCompliance()]
        if self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), IsPropertyAssignee()]
        return super().get_permissions()
```

### Role-Based Access Pattern

```python
class UserRole(models.TextChoices):
    VIEWER = 'viewer', 'Viewer'
    STAFF = 'staff', 'Staff'
    COMPLIANCE_OFFICER = 'compliance_officer', 'Compliance Officer'
    MANAGER = 'manager', 'Manager'
    ADMIN = 'admin', 'Administrator'


# Middleware or mixin that attaches role-based permissions
class RolePermissionMixin:
    """Mixin for views that need role-based access control."""
    
    required_role = None  # override in subclass
    
    ROLE_HIERARCHY = {
        'viewer': 0,
        'staff': 1,
        'compliance_officer': 2,
        'manager': 3,
        'admin': 4,
    }
    
    def dispatch(self, request, *args, **kwargs):
        if self.required_role:
            user_level = self.ROLE_HIERARCHY.get(request.user.role, 0)
            required_level = self.ROLE_HIERARCHY.get(self.required_role, 0)
            if user_level < required_level:
                raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
```

## Security Settings Checklist

```python
# settings/production.py

# HTTPS
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Security headers
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Sessions
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_COOKIE_HTTPONLY = True
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'

# Secrets
SECRET_KEY = env('DJANGO_SECRET_KEY')  # NEVER hardcode
DEBUG = False  # NEVER True in production

# Allowed hosts
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')  # explicit list, never ['*']
```

## CORS Configuration

```python
# settings/base.py
INSTALLED_APPS = [
    ...
    'corsheaders',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # must be high in the list
    'django.middleware.common.CommonMiddleware',
    ...
]

# settings/development.py
CORS_ALLOW_ALL_ORIGINS = True  # only in development

# settings/production.py
CORS_ALLOWED_ORIGINS = [
    'https://app.example.com',
    'https://portal.example.com',
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'authorization',
    'content-type',
    'x-csrftoken',
]
```

## Rate Limiting

```python
# Using django-ratelimit for view-level limiting
from django_ratelimit.decorators import ratelimit


@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def submit_document(request):
    """Limit document submissions to prevent abuse."""
    ...


# Using DRF's built-in throttling
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '20/hour',
        'user': '100/hour',
    },
}

# Custom throttle for sensitive endpoints
from rest_framework.throttling import UserRateThrottle


class BurstRateThrottle(UserRateThrottle):
    rate = '5/minute'


class PropertyViewSet(viewsets.ModelViewSet):
    def get_throttles(self):
        if self.action in ['create', 'update', 'destroy']:
            return [BurstRateThrottle()]
        return super().get_throttles()
```

## Input Validation and Sanitization

Django and DRF handle most input validation, but be explicit about boundaries.

```python
# Model-level validation (always runs)
from django.core.validators import RegexValidator, MinValueValidator

parcel_id = models.CharField(
    max_length=20,
    validators=[
        RegexValidator(
            regex=r'^\d{2}-\d{2}-\d{3}-\d{3}$',
            message='Parcel ID must match format XX-XX-XXX-XXX',
        ),
    ],
)

purchase_price = models.DecimalField(
    max_digits=12, decimal_places=2,
    validators=[MinValueValidator(Decimal('0.01'))],
)


# Serializer-level validation (API-specific rules)
class PropertySerializer(serializers.ModelSerializer):
    def validate_purchase_date(self, value):
        if value > date.today():
            raise serializers.ValidationError('Purchase date cannot be in the future.')
        return value
    
    def validate(self, data):
        """Cross-field validation."""
        if data.get('program') == 'featured_homes' and not data.get('purchase_price'):
            raise serializers.ValidationError({
                'purchase_price': 'Purchase price is required for Featured Homes.'
            })
        return data
```

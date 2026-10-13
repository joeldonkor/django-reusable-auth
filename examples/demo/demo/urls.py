from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    # All the package's endpoints: /api/auth/login/, /api/auth/register/, ...
    path("api/", include("reusable_auth.urls")),
    # Interactive API docs (needs `pip install django-reusable-auth[openapi]`)
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

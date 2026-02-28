from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as media_serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
]

# Serve media files during local development (including local HTTPS helper).
# `static()` only works when DEBUG=True, so we add an explicit route when
# local dev is enabled but DEBUG=False.
if getattr(settings, 'SERVE_MEDIA_IN_DEV', settings.DEBUG):
    if settings.DEBUG:
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    else:
        media_prefix = settings.MEDIA_URL.lstrip('/').rstrip('/')
        urlpatterns += [
            re_path(
                rf'^{media_prefix}/(?P<path>.*)$',
                media_serve,
                {'document_root': settings.MEDIA_ROOT},
            )
        ]

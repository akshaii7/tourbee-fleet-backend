from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.accounts.urls')),
    path('api/drivers/', include('apps.drivers.urls')),
    path('api/vehicles/', include('apps.vehicles.urls')),
    path('api/submissions/', include('apps.submissions.urls')),
    path('api/finance/', include('apps.finance.urls')),
    path('api/maintenance/', include('apps.maintenance.urls')),
    path('api/reports/', include('apps.reports.urls')),
    path('api/fleet/', include('fleet.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

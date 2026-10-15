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

from django.urls import re_path
from django.views.static import serve
from django.http import HttpResponse

def media_serve_cors(request, path):
    if request.method == 'OPTIONS':
        res = HttpResponse()
        res['Access-Control-Allow-Origin'] = '*'
        res['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        res['Access-Control-Allow-Headers'] = '*'
        return res
    response = serve(request, path, document_root=settings.MEDIA_ROOT)
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = '*'
    return response

urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', media_serve_cors),
    re_path(r'^api/media/(?P<path>.*)$', media_serve_cors),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


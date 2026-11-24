from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('sampletext.urls')),
    path('api/', include('sampletext.api_urls')),
]
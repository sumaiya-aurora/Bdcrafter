from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from shop.sitemaps import sitemaps

urlpatterns = [
    path('admin/', admin.site.urls),
    path('store-admin/', include('admin_panel.urls', namespace='admin_panel')),
    path('', include('shop.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('robots.txt', TemplateView.as_view(template_name='shop/robots.txt', content_type='text/plain')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Category, Product


class StaticViewSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.6

    def items(self):
        return [
            'shop:home',
            'shop:product_list',
            'shop:about',
            'shop:contact',
            'shop:faq',
            'shop:privacy',
            'shop:terms',
            'shop:shipping_policy',
            'shop:returns_policy',
        ]

    def location(self, item):
        return reverse(item)


class CategorySitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return Category.objects.filter(
            products__published=True,
            products__draft=False,
        ).distinct().order_by('name')


class ProductSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8
    lastmod = 'updated_at'

    def items(self):
        return Product.objects.filter(published=True, draft=False).select_related('category')


sitemaps = {
    'static': StaticViewSitemap,
    'categories': CategorySitemap,
    'products': ProductSitemap,
}

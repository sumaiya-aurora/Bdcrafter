import json

from django.db import models
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    WishlistItem,
    CartItem,
    Category,
    StorefrontContent,
    HeaderNavigationLink,
    FooterNavigationLink,
    HomepageTrustFeature,
)
from django.conf import settings


STORE_CATEGORY_SLUGS = (
    'kushikata',
    'gadgets',
    'digital-services',
    'clothes',
    'perfume',
    'organic-store',
)


def get_store_categories():
    categories = {
        category.slug: category
        for category in Category.objects.filter(slug__in=STORE_CATEGORY_SLUGS)
    }
    return [
        categories[slug]
        for slug in STORE_CATEGORY_SLUGS
        if slug in categories
    ]


def cart_and_wishlist(request):
    """
    Provides cart and wishlist counts to all templates.
    Supports both authenticated users and guests (session-based cart).
    """
    cart_items = []
    cart_count = 0
    wishlist_count = 0
    wishlist_items = []

    if request.user.is_authenticated:
        # Merge session cart into user cart on login
        session_key = request.session.session_key
        if session_key:
            session_cart = CartItem.objects.filter(session_id=session_key, user__isnull=True)
            for item in session_cart:
                existing = CartItem.objects.filter(user=request.user, product=item.product, variant=item.variant).first()
                if existing:
                    existing.quantity += item.quantity
                    existing.save()
                    item.delete()
                else:
                    item.user = request.user
                    item.session_id = None
                    item.save()

        cart_items = CartItem.objects.filter(user=request.user)
        cart_count = cart_items.aggregate(total=models.Sum('quantity'))['total'] or 0
        wishlist_items = WishlistItem.objects.filter(user=request.user)
        wishlist_count = wishlist_items.count()
    else:
        # Guest cart via session
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key
        if session_key:
            cart_items = CartItem.objects.filter(session_id=session_key, user__isnull=True)
            cart_count = cart_items.aggregate(total=models.Sum('quantity'))['total'] or 0

    return {
        'cart_items_global': cart_items,
        'cart_count': cart_count,
        'wishlist_count': wishlist_count,
        'wishlist_items': wishlist_items,
    }


def get_storefront_content():
    content, created = StorefrontContent.objects.get_or_create(pk=1)
    if created:
        HeaderNavigationLink.objects.bulk_create([
            HeaderNavigationLink(content=content, label='Home', url='/', placement='mobile', sort_order=0),
            HeaderNavigationLink(content=content, label='Shop', url='/products/', placement='both', sort_order=1),
            HeaderNavigationLink(content=content, label='Track Order', url='/order-tracking/', placement='both', sort_order=2),
            HeaderNavigationLink(content=content, label='About', url='/about/', placement='both', sort_order=3),
            HeaderNavigationLink(content=content, label='Contact', url='/contact/', placement='both', sort_order=4),
            HeaderNavigationLink(content=content, label='FAQ', url='/faq/', placement='both', sort_order=5),
        ])
        FooterNavigationLink.objects.bulk_create([
            FooterNavigationLink(content=content, section='quick', label='Shop All', url='/products/', sort_order=0),
            FooterNavigationLink(content=content, section='quick', label='Track Order', url='/order-tracking/', sort_order=1),
            FooterNavigationLink(content=content, section='quick', label='About Us', url='/about/', sort_order=2),
            FooterNavigationLink(content=content, section='quick', label='Contact', url='/contact/', sort_order=3),
            FooterNavigationLink(content=content, section='quick', label='FAQ', url='/faq/', sort_order=4),
            FooterNavigationLink(content=content, section='policy', label='Privacy Policy', url='/policies/privacy/', sort_order=0),
            FooterNavigationLink(content=content, section='policy', label='Terms & Conditions', url='/policies/terms/', sort_order=1),
            FooterNavigationLink(content=content, section='policy', label='Shipping Policy', url='/policies/shipping/', sort_order=2),
            FooterNavigationLink(content=content, section='policy', label='Return Policy', url='/policies/returns/', sort_order=3),
        ])
        HomepageTrustFeature.objects.bulk_create([
            HomepageTrustFeature(
                content=content, icon='truck', title='Free Delivery',
                description='Doorstep dispatch across Bangladesh.', sort_order=0,
            ),
            HomepageTrustFeature(
                content=content, icon='wallet', title='Cash on Delivery',
                description='Pay when you receive your order.', sort_order=1,
            ),
            HomepageTrustFeature(
                content=content, icon='check-circle', title='Quality Checked',
                description='Reliable products with every order.', sort_order=2,
            ),
            HomepageTrustFeature(
                content=content, icon='rotate', title='Easy Returns',
                description='Hassle-free 7-day returns.', sort_order=3,
            ),
        ])
    return content


def store_settings(request):
    """Provides store settings to all templates."""
    content = get_storefront_content()
    content = StorefrontContent.objects.prefetch_related(
        'header_links',
        'footer_links',
        'trust_features',
    ).get(pk=content.pk)
    return {
        'STORE_NAME': getattr(settings, 'STORE_NAME', 'Bdcrafter.com'),
        'STORE_PHONE': getattr(settings, 'STORE_PHONE', '+880 1234 567890'),
        'STORE_ADDRESS': getattr(settings, 'STORE_ADDRESS', 'Dhaka, Bangladesh'),
        'STORE_CATEGORIES': get_store_categories(),
        'site_content': content,
        'default_og_image': request.build_absolute_uri(content.hero_background_url),
    }


def _json_ld(data):
    serialized = json.dumps(data, ensure_ascii=False)
    serialized = (
        serialized
        .replace('&', '\\u0026')
        .replace('<', '\\u003c')
        .replace('>', '\\u003e')
        .replace('\u2028', '\\u2028')
        .replace('\u2029', '\\u2029')
    )
    return mark_safe(serialized)


def seo_metadata(request):
    """Adds canonical, crawl directives, and site-level structured data."""
    route_name = getattr(getattr(request, 'resolver_match', None), 'url_name', None)
    noindex_routes = {
        'cart_detail', 'checkout', 'order_success', 'order_tracking',
        'order_detail', 'order_history', 'dashboard', 'profile',
        'address_list', 'address_add', 'address_edit', 'address_delete',
        'wishlist_detail', 'register', 'activation_sent', 'activate',
        'login', 'logout', 'password_reset', 'password_reset_done',
        'password_reset_confirm', 'password_reset_complete',
        'password_change', 'password_change_done', 'search',
    }
    noindex = route_name in noindex_routes
    if route_name == 'product_list':
        noindex = noindex or any(
            request.GET.get(key)
            for key in ('q', 'brand', 'min_price', 'max_price', 'sort')
        )

    base_url = request.build_absolute_uri('/')
    search_url = f"{request.build_absolute_uri(reverse('shop:search'))}?q={{search_term_string}}"
    website_schema = _json_ld({
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        'name': getattr(settings, 'STORE_NAME', 'Bdcrafter.com'),
        'url': base_url,
        'potentialAction': {
            '@type': 'SearchAction',
            'target': search_url,
            'query-input': 'required name=search_term_string',
        },
    })
    return {
        'canonical_url': request.build_absolute_uri(request.path),
        'seo_robots': 'noindex,follow' if noindex else 'index,follow',
        'website_schema': website_schema,
    }

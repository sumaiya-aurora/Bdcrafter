"""
Custom admin panel views for Bdcrafter.com.
All routes are staff-only (@staff_required).
"""
import logging
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.forms import inlineformset_factory

from django.conf import settings
from shop.forms import (
    AdminProductForm,
    FooterNavigationLinkForm,
    HeaderNavigationLinkForm,
    HomepageTrustFeatureForm,
    StorefrontContentForm,
)
from shop.context_processors import get_storefront_content
from shop.emails import send_customer_invoice
from shop.models import (
    Order, OrderItem, Product, ProductImage, ProductVariant,
    Category, Brand, CartItem, FooterNavigationLink, HeaderNavigationLink,
    HomepageTrustFeature, StorefrontContent,
)

logger = logging.getLogger(__name__)

HeaderNavigationFormSet = inlineformset_factory(
    StorefrontContent,
    HeaderNavigationLink,
    form=HeaderNavigationLinkForm,
    extra=0,
    can_delete=True,
)
FooterNavigationFormSet = inlineformset_factory(
    StorefrontContent,
    FooterNavigationLink,
    form=FooterNavigationLinkForm,
    extra=0,
    can_delete=True,
)
HomepageTrustFeatureFormSet = inlineformset_factory(
    StorefrontContent,
    HomepageTrustFeature,
    form=HomepageTrustFeatureForm,
    extra=0,
    can_delete=True,
)


# ─────────────────────────────────────
# Dashboard
# ─────────────────────────────────────

@staff_member_required(login_url='/accounts/login/')
def admin_dashboard(request):
    from decimal import Decimal
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status='pending').count()
    new_orders = Order.objects.filter(is_new=True).count()
    order_values = Order.objects.exclude(status='cancelled')
    total_revenue = order_values.filter(currency='BDT').aggregate(
        rev=Sum('total')
    )['rev'] or Decimal('0')
    total_revenue_usd = order_values.filter(currency='USD').aggregate(
        rev=Sum('total')
    )['rev'] or Decimal('0')

    recent_orders = Order.objects.select_related('user').order_by('-created_at')[:10]
    low_stock = Product.objects.filter(published=True, draft=False, stock__lte=5).order_by('stock')[:10]

    # Orders by status for quick view
    status_counts = {
        'pending': Order.objects.filter(status='pending').count(),
        'confirmed': Order.objects.filter(status='confirmed').count(),
        'shipped': Order.objects.filter(status='shipped').count(),
        'delivered': Order.objects.filter(status='delivered').count(),
        'cancelled': Order.objects.filter(status='cancelled').count(),
    }

    return render(request, 'admin_panel/dashboard.html', {
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'new_orders': new_orders,
        'total_revenue': total_revenue,
        'total_revenue_usd': total_revenue_usd,
        'recent_orders': recent_orders,
        'low_stock': low_stock,
        'status_counts': status_counts,
        'page': 'dashboard',
    })


@staff_member_required(login_url='/accounts/login/')
def admin_storefront_content(request):
    content = get_storefront_content()

    if request.method == 'POST':
        content_form = StorefrontContentForm(request.POST, instance=content)
        header_formset = HeaderNavigationFormSet(request.POST, instance=content, prefix='header')
        footer_formset = FooterNavigationFormSet(request.POST, instance=content, prefix='footer')
        feature_formset = HomepageTrustFeatureFormSet(request.POST, instance=content, prefix='feature')

        forms_valid = [
            content_form.is_valid(),
            header_formset.is_valid(),
            footer_formset.is_valid(),
            feature_formset.is_valid(),
        ]
        if all(forms_valid):
            with transaction.atomic():
                content_form.save()
                header_formset.save()
                footer_formset.save()
                feature_formset.save()
            messages.success(request, 'Homepage and footer content saved.')
            return redirect('admin_panel:storefront_content')
    else:
        content_form = StorefrontContentForm(instance=content)
        header_formset = HeaderNavigationFormSet(instance=content, prefix='header')
        footer_formset = FooterNavigationFormSet(instance=content, prefix='footer')
        feature_formset = HomepageTrustFeatureFormSet(instance=content, prefix='feature')

    field_groups = [
        ('Brand', ['brand_name', 'brand_suffix', 'brand_url']),
        ('Homepage hero', [
            'hero_eyebrow', 'hero_background_url', 'hero_title_lead',
            'hero_title_emphasis', 'hero_description_prefix', 'hero_brand_text',
            'hero_description_suffix', 'hero_primary_label', 'hero_primary_url',
            'hero_secondary_label', 'hero_secondary_url',
        ]),
        ('Hero side card copy', [
            'hero_card_eyebrow', 'hero_card_title_lead', 'hero_card_title_emphasis',
            'hero_card_tag_one', 'hero_card_tag_two', 'hero_card_tag_three',
            'hero_card_footer',
        ]),
        ('Homepage sections', [
            'home_category_heading', 'home_category_link_label', 'home_category_link_url',
            'home_featured_heading', 'home_featured_link_label', 'home_featured_link_url',
            'home_arrivals_heading', 'home_arrivals_link_label', 'home_arrivals_link_url',
            'home_product_view_label', 'home_product_new_badge', 'home_product_sale_badge',
        ]),
        ('Homepage call to action', [
            'home_cta_eyebrow', 'home_cta_title', 'home_cta_description',
            'home_cta_button_label', 'home_cta_button_url', 'home_cta_background_url',
        ]),
        ('Footer copy', [
            'footer_brand_description', 'footer_quick_links_heading',
            'footer_policies_heading', 'footer_contact_heading', 'footer_country_text',
            'footer_copyright_text',
        ]),
        ('Footer contact details', [
            'footer_address_text', 'footer_address_url', 'footer_phone_text',
            'footer_phone_url', 'footer_email_text', 'footer_email_url',
            'footer_whatsapp_text', 'footer_whatsapp_url', 'footer_facebook_label',
            'footer_facebook_url', 'footer_instagram_label', 'footer_instagram_url',
        ]),
    ]
    return render(request, 'admin_panel/storefront_content.html', {
        'content_form': content_form,
        'field_groups': [
            (title, [content_form[name] for name in field_names])
            for title, field_names in field_groups
        ],
        'inlines': [
            ('Header navigation links', header_formset),
            ('Footer navigation links', footer_formset),
            ('Homepage trust features', feature_formset),
        ],
        'new_count': Order.objects.filter(is_new=True).count(),
        'page': 'storefront',
    })


# ─────────────────────────────────────
# Orders
# ─────────────────────────────────────

@staff_member_required(login_url='/accounts/login/')
def admin_orders(request):
    orders = Order.objects.select_related('user').order_by('-created_at')

    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('q', '').strip()

    if status_filter:
        orders = orders.filter(status=status_filter)
    if search:
        orders = orders.filter(
            Q(order_number__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search)
        )

    new_count = Order.objects.filter(is_new=True).count()

    return render(request, 'admin_panel/orders.html', {
        'orders': orders,
        'status_filter': status_filter,
        'search': search,
        'new_count': new_count,
        'page': 'orders',
        'STATUS_CHOICES': Order.STATUS_CHOICES,
    })


@staff_member_required(login_url='/accounts/login/')
def admin_order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    new_count = Order.objects.filter(is_new=True).count()

    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status and new_status in dict(Order.STATUS_CHOICES):
            old_status = order.status
            order.status = new_status
            order.is_new = False
            order.save()
            if old_status == 'pending' and new_status == 'confirmed':
                send_customer_invoice(order)
            messages.success(request, f'Order status updated: {old_status} → {new_status}')
        return redirect('admin_panel:order_detail', order_id=order.id)

    return render(request, 'admin_panel/order_detail.html', {
        'order': order,
        'new_count': new_count,
        'page': 'orders',
        'STATUS_CHOICES': Order.STATUS_CHOICES,
    })


@staff_member_required(login_url='/accounts/login/')
def admin_order_invoice(request, order_id):
    """Clean printable invoice view for printing or downloading."""
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'admin_panel/order_invoice.html', {
        'order': order,
        'store_name': getattr(settings, 'STORE_NAME', 'Bdcrafter.com'),
        'store_phone': getattr(settings, 'STORE_PHONE', '+880 1234 567890'),
        'store_address': getattr(settings, 'STORE_ADDRESS', 'Dhaka, Bangladesh'),
        'admin_email': getattr(settings, 'ADMIN_EMAIL', 'admin@bdcrafter.com'),
    })


# ─────────────────────────────────────
# Products
# ─────────────────────────────────────

@staff_member_required(login_url='/accounts/login/')
def admin_products(request):
    products = Product.objects.select_related('category', 'brand').order_by('-created_at')
    search = request.GET.get('q', '').strip()
    if search:
        products = products.filter(Q(name__icontains=search) | Q(sku__icontains=search))

    new_count = Order.objects.filter(is_new=True).count()
    return render(request, 'admin_panel/products.html', {
        'products': products,
        'search': search,
        'new_count': new_count,
        'page': 'products',
    })


@staff_member_required(login_url='/accounts/login/')
def admin_product_add(request):
    """Add a new product with category, price, stock, images, etc."""
    new_count = Order.objects.filter(is_new=True).count()
    if request.method == 'POST':
        form = AdminProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product "{product.name}" created successfully!')
            return redirect('admin_panel:products')
    else:
        form = AdminProductForm()

    return render(request, 'admin_panel/product_form.html', {
        'form': form,
        'is_edit': False,
        'new_count': new_count,
        'page': 'products',
    })


@staff_member_required(login_url='/accounts/login/')
def admin_product_edit(request, product_id):
    """Edit an existing product or handle quick toggle actions."""
    product = get_object_or_404(Product, id=product_id)
    new_count = Order.objects.filter(is_new=True).count()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'toggle_published':
            product.published = not product.published
            product.save()
            state = 'published' if product.published else 'unpublished'
            messages.success(request, f'"{product.name}" is now {state}.')
            return redirect('admin_panel:products')
        elif action == 'toggle_featured':
            product.featured = not product.featured
            product.save()
            state = 'featured' if product.featured else 'unfeatured'
            messages.success(request, f'"{product.name}" {state}.')
            return redirect('admin_panel:products')

        form = AdminProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product "{product.name}" updated successfully!')
            return redirect('admin_panel:products')
    else:
        form = AdminProductForm(instance=product)

    return render(request, 'admin_panel/product_form.html', {
        'form': form,
        'product': product,
        'is_edit': True,
        'new_count': new_count,
        'page': 'products',
    })


@staff_member_required(login_url='/accounts/login/')
def admin_product_delete(request, product_id):
    """Delete a product after confirmation."""
    product = get_object_or_404(Product, id=product_id)
    new_count = Order.objects.filter(is_new=True).count()

    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f'Product "{name}" has been deleted.')
        return redirect('admin_panel:products')

    return render(request, 'admin_panel/product_confirm_delete.html', {
        'product': product,
        'new_count': new_count,
        'page': 'products',
    })

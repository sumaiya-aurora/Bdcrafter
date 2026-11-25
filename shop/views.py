import logging
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_encode, urlsafe_base64_decode
from django.views.decorators.http import require_POST

from .emails import notify_admin_new_order
from .forms import (
    AddressForm,
    ContactForm,
    GuestCheckoutForm,
    CouponApplyForm,
    ProfileForm,
    QuestionForm,
    ReviewForm,
    UserRegistrationForm,
)
from .context_processors import get_store_categories
from .models import (
    Address,
    CartItem,
    Category,
    Coupon,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    ProductImage,
    Question,
    Review,
    SubCategory,
    WishlistItem,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Cart helpers (supports guest + logged-in users)
# ──────────────────────────────────────────────

def _ensure_session(request):
    """Make sure a session key exists."""
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def get_cart_items(request):
    """Return CartItem queryset for current user (logged-in or guest)."""
    if request.user.is_authenticated:
        return CartItem.objects.filter(user=request.user)
    session_key = _ensure_session(request)
    return CartItem.objects.filter(session_id=session_key, user__isnull=True)


def _cart_currency_state(cart_items):
    currencies = {item.product.currency for item in cart_items}
    if len(currencies) > 1:
        return None, True
    return (next(iter(currencies)) if currencies else 'BDT'), False


# ──────────────────────────────────────────────
# Public pages
# ──────────────────────────────────────────────

def home(request):
    categories = get_store_categories()
    featured_products = Product.objects.filter(featured=True, published=True, draft=False).select_related('category', 'brand')[:4]
    new_arrivals = Product.objects.filter(published=True, draft=False).order_by('-created_at').select_related('category', 'brand')[:8]
    best_sellers = Product.objects.filter(published=True, draft=False).select_related('category', 'brand')[:8]
    services_by_name = {
        product.name: product
        for product in Product.objects.filter(
            category__slug='digital-services',
            name__in=['Portfolio Website', 'Ecommerce Site'],
            published=True,
            draft=False,
        ).select_related('category')
    }
    highlighted_services = [
        services_by_name[name]
        for name in ['Portfolio Website', 'Ecommerce Site']
        if name in services_by_name
    ]
    return render(request, 'shop/home.html', {
        'categories': categories,
        'featured_products': featured_products,
        'highlighted_services': highlighted_services,
        'new_arrivals': new_arrivals,
        'best_sellers': best_sellers,
    })


def product_list(request):
    products = Product.objects.filter(published=True, draft=False).select_related('category', 'brand')
    categories = get_store_categories()
    subcategories = SubCategory.objects.none()
    brands = Brand_list = sorted(set(
        Product.objects.filter(published=True, draft=False, brand__isnull=False).values_list('brand__name', flat=True)
    ))
    tags = sorted(set(
        v for v in Product.objects.filter(published=True, draft=False).values_list('tags__name', flat=True) if v
    ))

    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()
    subcategory_slug = request.GET.get('subcategory', '').strip()
    selected_category_name = next(
        (category.name for category in categories if category.slug == category_slug),
        '',
    )
    selected_category_obj = next(
        (category for category in categories if category.slug == category_slug),
        None,
    )
    brand_name = request.GET.get('brand', '').strip()
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()
    sort = request.GET.get('sort', '').strip()

    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query) |
            Q(sku__icontains=query) | Q(category__name__icontains=query) |
            Q(brand__name__icontains=query) | Q(tags__name__icontains=query)
        ).distinct()
    if category_slug:
        products = products.filter(category__slug=category_slug)
        subcategories = list(
            SubCategory.objects.filter(category__slug=category_slug).order_by('name')
        )
    selected_subcategory = next(
        (subcategory for subcategory in subcategories if subcategory.slug == subcategory_slug),
        None,
    )
    if subcategory_slug:
        products = products.filter(subcategory__slug=subcategory_slug)
    if brand_name:
        products = products.filter(brand__name=brand_name)
    if min_price:
        try:
            products = products.filter(price__gte=float(min_price))
        except ValueError:
            pass
    if max_price:
        try:
            products = products.filter(price__lte=float(max_price))
        except ValueError:
            pass

    if sort == 'price_asc':
        products = products.order_by('price')
    elif sort == 'price_desc':
        products = products.order_by('-price')
    elif sort == 'newest':
        products = products.order_by('-created_at')
    elif sort == 'best_selling':
        products = products.order_by('-stock')
    elif sort == 'highest_rated':
        products = sorted(products, key=lambda p: p.average_rating(), reverse=True)

    product_count = products.count() if hasattr(products, 'count') else len(products)
    query_params = request.GET.copy()
    query_params.pop('page', None)
    query_string = query_params.urlencode()
    page_obj = Paginator(products, 24).get_page(request.GET.get('page'))
    canonical_params = {}
    if selected_category_obj:
        canonical_params['category'] = selected_category_obj.slug
        if selected_subcategory:
            canonical_params['subcategory'] = selected_subcategory.slug
    if page_obj.number > 1:
        canonical_params['page'] = page_obj.number
    canonical_path = reverse('shop:product_list')
    if canonical_params:
        canonical_path = f'{canonical_path}?{urlencode(canonical_params)}'
    noindex_listing = (
        (category_slug and not selected_category_obj)
        or (subcategory_slug and not selected_subcategory)
        or any(request.GET.get(key) for key in ('q', 'brand', 'min_price', 'max_price', 'sort'))
    )

    return render(request, 'shop/product_list.html', {
        'products': page_obj,
        'page_obj': page_obj,
        'product_count': product_count,
        'pagination_query': f'{query_string}&' if query_string else '',
        'categories': categories,
        'subcategories': subcategories,
        'brands': brands,
        'tags': tags,
        'query': query,
        'selected_category': category_slug,
        'selected_subcategory': subcategory_slug,
        'selected_category_name': selected_category_name,
        'selected_category_description': selected_category_obj.description if selected_category_obj else '',
        'selected_brand': brand_name,
        'canonical_url': request.build_absolute_uri(canonical_path),
        'seo_robots': 'noindex,follow' if noindex_listing else 'index,follow',
    })


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, published=True, draft=False)
    images = product.images.all()
    related_products = Product.objects.filter(
        category=product.category, published=True, draft=False
    ).exclude(id=product.id).select_related('category', 'brand')[:4]
    reviews = product.reviews.filter(approved=True)
    questions = product.questions.order_by('-asked_at')[:8]
    review_form = ReviewForm()
    question_form = QuestionForm()
    primary_image = product.primary_image
    return render(request, 'shop/product_detail.html', {
        'product': product,
        'variants': product.variants.all(),
        'images': images,
        'primary_image': primary_image,
        'related_products': related_products,
        'reviews': reviews,
        'questions': questions,
        'review_form': review_form,
        'question_form': question_form,
        'og_image': (
            request.build_absolute_uri(primary_image.image.url)
            if primary_image else None
        ),
        'product_image_url': (
            request.build_absolute_uri(primary_image.image.url)
            if primary_image else ''
        ),
    })


def search(request):
    query = request.GET.get('q', '').strip()
    products = Product.objects.filter(published=True, draft=False).select_related('category', 'brand')
    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query) |
            Q(sku__icontains=query) | Q(category__name__icontains=query) |
            Q(brand__name__icontains=query) | Q(tags__name__icontains=query)
        ).distinct()
    else:
        products = products.none()

    if request.GET.get('format') == 'json':
        results = [{
            'name': product.name,
            'url': product.get_absolute_url(),
            'price': str(product.price_display),
            'currency': product.currency,
            'price_on_request': product.price_on_request,
            'image': product.featured_image.image.url if product.featured_image else '',
            'brand': product.brand.name if product.brand else '',
        } for product in products[:8]]
        return JsonResponse({'results': results, 'query': query})

    return render(request, 'shop/search_results.html', {'products': products, 'query': query})


# ──────────────────────────────────────────────
# Authentication
# ──────────────────────────────────────────────

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            activation_url = request.build_absolute_uri(reverse('shop:activate', args=[uid, token]))
            try:
                send_mail(
                    'Activate your Bdcrafter.com account',
                    f'Hi {user.username},\n\nWelcome to Bdcrafter.com. Activate your account: {activation_url}',
                    'Bdcrafter.com <support@bdcrafter.com>',
                    [user.email],
                    fail_silently=True,
                )
            except Exception as e:
                logger.error(f'Activation email failed: {e}')
            messages.success(request, 'Registration successful. Check your email to activate your account.')
            return redirect('shop:activation_sent')
    else:
        form = UserRegistrationForm()
    return render(request, 'shop/register.html', {'form': form})


def activation_sent(request):
    return render(request, 'shop/activation_sent.html')


def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        messages.success(request, 'Your account has been activated.')
        return render(request, 'shop/activation_complete.html')

    return render(request, 'shop/activation_invalid.html')


# ──────────────────────────────────────────────
# Cart  (works for guests and logged-in users)
# ──────────────────────────────────────────────

def cart_detail(request):
    cart_items = list(get_cart_items(request).select_related('product', 'product__category', 'variant'))
    currency, mixed_currency = _cart_currency_state(cart_items)
    subtotal = sum(item.total_price() for item in cart_items) if not mixed_currency else None
    return render(request, 'shop/cart.html', {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'cart_currency': currency,
        'mixed_currency': mixed_currency,
        'cart_requires_quote': any(item.product.price_on_request for item in cart_items),
        'cart_quote_only': any(item.product.price_on_request for item in cart_items) and subtotal == 0,
    })


@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id, published=True, draft=False)
    if any(
        item.product.currency != product.currency
        for item in get_cart_items(request).select_related('product')
    ):
        messages.error(
            request,
            'Your cart contains a different currency. Please complete or clear it before adding this item.',
        )
        return redirect('shop:cart_detail')

    variant_id = request.POST.get('variant') or request.GET.get('variant')
    variant = None
    if variant_id:
        variant = get_object_or_404(ProductVariant, id=variant_id, product=product)
    elif product.variants.exists():
        messages.error(request, 'Choose a product option before adding this item.')
        return redirect(product.get_absolute_url())

    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        quantity = 0
    stock = None if product.is_digital_service else (variant.stock if variant else product.stock)
    if quantity < 1:
        messages.error(request, 'Enter a valid quantity.')
        return redirect(product.get_absolute_url())

    if request.user.is_authenticated:
        cart_item, created = CartItem.objects.get_or_create(
            user=request.user, product=product, variant=variant,
            defaults={'quantity': quantity, 'session_id': None}
        )
    else:
        session_key = _ensure_session(request)
        cart_item, created = CartItem.objects.get_or_create(
            session_id=session_key, user=None, product=product, variant=variant,
            defaults={'quantity': quantity}
        )

    if not created:
        quantity += cart_item.quantity
    if stock is not None and quantity > stock:
        if created:
            cart_item.delete()
        messages.error(request, f'Only {stock} unit(s) are currently available.')
        return redirect(product.get_absolute_url())
    if not created:
        cart_item.quantity = quantity
        cart_item.save(update_fields=['quantity'])

    messages.success(request, f'"{product.name}" added to your cart.')
    next_url = request.POST.get('next', '')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect('shop:cart_detail')


@require_POST
def cart_remove(request, item_id):
    if request.user.is_authenticated:
        cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)
    else:
        session_key = _ensure_session(request)
        cart_item = get_object_or_404(CartItem, id=item_id, session_id=session_key, user__isnull=True)
    cart_item.delete()
    messages.success(request, 'Item removed from cart.')
    return redirect('shop:cart_detail')


@require_POST
def cart_update(request, item_id):
    if request.user.is_authenticated:
        cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)
    else:
        session_key = _ensure_session(request)
        cart_item = get_object_or_404(CartItem, id=item_id, session_id=session_key, user__isnull=True)

    try:
        quantity = int(request.POST.get('quantity', 0))
    except (TypeError, ValueError):
        quantity = 0
    stock = None if cart_item.product.is_digital_service else (
        cart_item.variant.stock if cart_item.variant else cart_item.product.stock
    )
    if quantity < 1:
        messages.error(request, 'Choose a quantity of at least 1.')
        return redirect('shop:cart_detail')
    if stock is not None and quantity > stock:
        messages.error(request, f'Choose a quantity between 1 and {stock}.')
        return redirect('shop:cart_detail')
    cart_item.quantity = quantity
    cart_item.save()
    messages.success(request, 'Cart updated.')
    return redirect('shop:cart_detail')


# ──────────────────────────────────────────────
# Wishlist (requires login)
# ──────────────────────────────────────────────

@login_required
def wishlist_detail(request):
    items = WishlistItem.objects.filter(user=request.user).select_related('product')
    return render(request, 'shop/wishlist.html', {'items': items})


def wishlist_add(request, product_id):
    product = get_object_or_404(Product, id=product_id, published=True, draft=False)
    if not request.user.is_authenticated:
        messages.error(request, 'Please log in to use your wishlist.')
        return redirect('login')
    WishlistItem.objects.get_or_create(user=request.user, product=product)
    messages.success(request, f'"{product.name}" added to your wishlist.')
    return redirect(request.META.get('HTTP_REFERER', 'shop:wishlist_detail'))


def wishlist_remove(request, item_id):
    item = get_object_or_404(WishlistItem, id=item_id, user=request.user)
    item.delete()
    messages.success(request, 'Removed from wishlist.')
    return redirect('shop:wishlist_detail')


def wishlist_move_to_cart(request, item_id):
    item = get_object_or_404(WishlistItem, id=item_id, user=request.user)
    if any(
        cart_item.product.currency != item.product.currency
        for cart_item in get_cart_items(request).select_related('product')
    ):
        messages.error(
            request,
            'Your cart contains a different currency. Please complete or clear it before adding this item.',
        )
        return redirect('shop:cart_detail')
    CartItem.objects.get_or_create(user=request.user, product=item.product, variant=None, defaults={'quantity': 1})
    item.delete()
    messages.success(request, f'"{item.product.name}" moved to cart.')
    return redirect('shop:wishlist_detail')


# ──────────────────────────────────────────────
# Checkout — GUEST CHECKOUT (no login required)
# ──────────────────────────────────────────────

def checkout(request):
    """
    Checkout view — works for both guests and logged-in users.
    No login required. Cart is session-based for guests.
    """
    cart_items = list(
        get_cart_items(request).select_related('product', 'product__category', 'variant')
    )
    if not cart_items:
        messages.warning(request, 'Your cart is empty.')
        return redirect('shop:product_list')

    cart_currency, mixed_currency = _cart_currency_state(cart_items)
    if mixed_currency:
        messages.error(
            request,
            'Your cart contains different currencies. Complete separate orders for BDT and USD items.',
        )
        return redirect('shop:cart_detail')

    requires_quote = any(item.product.price_on_request for item in cart_items)
    subtotal = sum(item.total_price() for item in cart_items)
    shipping_cost = 0  # Free shipping — adjust as needed

    if request.method == 'POST':
        form = GuestCheckoutForm(request.POST)
        if cart_currency == 'USD':
            form.fields['payment_method'].choices = [
                ('post_order', 'Payment details after order'),
            ]
            form.fields['payment_method'].initial = 'post_order'
        if form.is_valid():
            with transaction.atomic():
                inventory = []
                for item in cart_items:
                    if item.product.is_digital_service:
                        continue
                    if item.variant_id:
                        stock_item = ProductVariant.objects.select_for_update().get(
                            pk=item.variant_id, product_id=item.product_id
                        )
                    else:
                        stock_item = Product.objects.select_for_update().get(pk=item.product_id)
                    if item.quantity > stock_item.stock:
                        messages.error(
                            request,
                            f'Only {stock_item.stock} unit(s) of "{item.product.name}" are available. Update your cart.',
                        )
                        return redirect('shop:cart_detail')
                    inventory.append((stock_item, item.quantity))

                coupon = None
                discount = 0
                code = form.cleaned_data.get('coupon_code', '').strip()
                if code and cart_currency != 'BDT':
                    messages.warning(request, 'Coupons are only available for BDT orders.')
                elif code:
                    coupon = Coupon.objects.select_for_update().filter(code__iexact=code, active=True).first()
                    if coupon and coupon.is_valid():
                        discount = coupon.discount_value(subtotal)
                        coupon.used_count += 1
                        coupon.save(update_fields=['used_count'])
                    else:
                        messages.warning(request, 'Coupon code is not valid or has expired.')
                        coupon = None

                total = subtotal - discount + shipping_cost
                order = Order.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    session_key=request.session.session_key or '',
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    email=form.cleaned_data['email'],
                    phone=form.cleaned_data['phone'],
                    shipping_address=form.cleaned_data['shipping_address'],
                    shipping_city=form.cleaned_data['shipping_city'],
                    shipping_state=form.cleaned_data.get('shipping_state', ''),
                    shipping_postal_code=form.cleaned_data.get('shipping_postal_code', ''),
                    shipping_country=form.cleaned_data.get('shipping_country', 'Bangladesh'),
                    billing_address=form.cleaned_data['shipping_address'],
                    billing_city=form.cleaned_data['shipping_city'],
                    billing_state=form.cleaned_data.get('shipping_state', ''),
                    billing_postal_code=form.cleaned_data.get('shipping_postal_code', ''),
                    billing_country=form.cleaned_data.get('shipping_country', 'Bangladesh'),
                    note=form.cleaned_data.get('order_notes', ''),
                    coupon=coupon,
                    discount=discount,
                    shipping_cost=shipping_cost,
                    total=total,
                    currency=cart_currency,
                    requires_quote=requires_quote,
                    payment_method=dict(form.fields['payment_method'].choices).get(
                        form.cleaned_data['payment_method'], form.cleaned_data['payment_method']
                    ),
                    payment_status='Pending',
                    status='pending',
                    is_new=True,
                )

                for item in cart_items:
                    OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        variant=item.variant,
                        product_name=item.product.name,
                        variant_name=item.variant.name if item.variant else '',
                        quantity=item.quantity,
                        unit_price=item.variant.price_display if item.variant else item.product.price_display,
                    )
                for stock_item, quantity in inventory:
                    stock_item.stock -= quantity
                    stock_item.save(update_fields=['stock'])
                get_cart_items(request).delete()

            # Notify the admin; the customer invoice is sent after confirmation.
            notify_admin_new_order(order)

            messages.success(request, f'Order #{order.order_number} placed successfully! We will email your invoice after confirming your order.')

            # Store order number in session so guest can access their order
            if not request.user.is_authenticated:
                guest_orders = request.session.get('guest_orders', [])
                guest_orders.append(order.order_number)
                request.session['guest_orders'] = guest_orders

            return redirect('shop:order_success', order_number=order.order_number)
    else:
        # Pre-fill form for logged-in users
        initial = {'shipping_country': 'Bangladesh'}
        if request.user.is_authenticated:
            initial.update({
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'email': request.user.email,
            })
        form = GuestCheckoutForm(initial=initial)
        if cart_currency == 'USD':
            form.fields['payment_method'].choices = [
                ('post_order', 'Payment details after order'),
            ]
            form.fields['payment_method'].initial = 'post_order'

    return render(request, 'shop/checkout.html', {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'shipping_cost': shipping_cost,
        'total': subtotal + shipping_cost,
        'cart_currency': cart_currency,
        'cart_requires_quote': requires_quote,
        'cart_quote_only': requires_quote and subtotal == 0,
        'form': form,
    })


def order_success(request, order_number):
    """Order success / thank-you page. Accessible to guests via session."""
    order = get_object_or_404(Order, order_number=order_number)

    # Security: only the owner or the guest who placed it can view
    can_view = False
    if request.user.is_authenticated and order.user == request.user:
        can_view = True
    elif not request.user.is_authenticated or order.user is None:
        # Check guest_orders in session
        guest_orders = request.session.get('guest_orders', [])
        if order_number in guest_orders:
            can_view = True
    if not can_view and request.user.is_authenticated and request.user.is_staff:
        can_view = True

    if not can_view:
        messages.error(request, 'Order not found or access denied.')
        return redirect('shop:home')

    return render(request, 'shop/order_success.html', {'order': order})


def order_tracking(request):
    order = None
    searched = False
    input_order_id = ''
    if request.method == 'POST':
        searched = True
        input_order_id = request.POST.get(
            'order_id',
            request.POST.get('order_number', ''),
        ).strip()
        if input_order_id:
            order_lookup = Q(order_number__iexact=input_order_id)
            if input_order_id.isdigit():
                order_lookup |= Q(pk=input_order_id)
            order = Order.objects.filter(order_lookup).first()

    response = render(request, 'shop/order_tracking.html', {
        'order': order,
        'searched': searched,
        'input_order_id': input_order_id,
    })
    response['Cache-Control'] = 'no-store'
    return response


@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user)
    return render(request, 'shop/order_history.html', {'orders': orders})


def order_detail(request, order_id):
    """Order detail page — accessible to order owner or admin."""
    if request.user.is_authenticated:
        if request.user.is_staff:
            order = get_object_or_404(Order, id=order_id)
        else:
            order = get_object_or_404(Order, id=order_id, user=request.user)
    else:
        # Guest: check session
        order = get_object_or_404(Order, id=order_id)
        guest_orders = request.session.get('guest_orders', [])
        if order.order_number not in guest_orders:
            messages.error(request, 'Please log in to view your order.')
            return redirect('login')
    return render(request, 'shop/order_detail.html', {'order': order})


@login_required
def order_cancel(request, order_id):
    if request.user.is_staff:
        order = get_object_or_404(Order, id=order_id)
    else:
        order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.can_cancel():
        order.status = 'cancelled'
        order.save()
        messages.success(request, f'Order #{order.order_number} has been cancelled.')
    else:
        messages.warning(request, 'This order cannot be cancelled at this stage.')
    return redirect('shop:order_detail', order_id=order.id)


# ──────────────────────────────────────────────
# User account
# ──────────────────────────────────────────────

@login_required
def dashboard(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')[:5]
    wishlist = WishlistItem.objects.filter(user=request.user).select_related('product')[:5]
    return render(request, 'shop/dashboard.html', {'orders': orders, 'wishlist': wishlist})


@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('shop:profile')
    else:
        form = ProfileForm(instance=request.user)
    return render(request, 'shop/profile.html', {'form': form})


@login_required
def address_list(request):
    addresses = Address.objects.filter(user=request.user)
    return render(request, 'shop/address_list.html', {'addresses': addresses})


@login_required
def address_add(request):
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            messages.success(request, 'Address added.')
            return redirect('shop:address_list')
    else:
        form = AddressForm()
    return render(request, 'shop/address_form.html', {'form': form})


@login_required
def address_edit(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, 'Address updated.')
            return redirect('shop:address_list')
    else:
        form = AddressForm(instance=address)
    return render(request, 'shop/address_form.html', {'form': form})


@login_required
def address_delete(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    address.delete()
    messages.success(request, 'Address removed.')
    return redirect('shop:address_list')


# ──────────────────────────────────────────────
# Reviews & Questions
# ──────────────────────────────────────────────

def submit_review(request, product_id):
    product = get_object_or_404(Product, id=product_id, published=True, draft=False)
    if request.method == 'POST' and request.user.is_authenticated:
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            review.product = product
            review.verified_purchase = True
            review.save()
            messages.success(request, 'Review submitted. Thank you!')
        else:
            messages.error(request, 'Review could not be submitted. Please check your input.')
    elif not request.user.is_authenticated:
        messages.error(request, 'Please log in to submit a review.')
    return redirect('shop:product_detail', slug=product.slug)


def submit_question(request, product_id):
    product = get_object_or_404(Product, id=product_id, published=True, draft=False)
    if request.method == 'POST' and request.user.is_authenticated:
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.user = request.user
            question.product = product
            question.save()
            messages.success(request, 'Your question has been posted.')
    elif not request.user.is_authenticated:
        messages.error(request, 'Please log in to ask a question.')
    return redirect('shop:product_detail', slug=product.slug)


def apply_coupon(request):
    if request.method == 'POST':
        form = CouponApplyForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            messages.info(request, f'Coupon "{code}" will be applied at checkout.')
    return redirect('shop:checkout')


# ──────────────────────────────────────────────
# Static pages
# ──────────────────────────────────────────────

def about(request):
    return render(request, 'shop/about.html')


def contact(request):
    form = ContactForm()
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            # In production, send this to admin email
            from django.conf import settings
            try:
                send_mail(
                    f"Bdcrafter.com Contact Form: {form.cleaned_data['subject']}",
                    f"From: {form.cleaned_data['name']} <{form.cleaned_data['email']}>\n\n{form.cleaned_data['message']}",
                    settings.FROM_EMAIL,
                    [settings.ADMIN_EMAIL],
                    fail_silently=True,
                )
            except Exception as e:
                logger.error(f'Contact form email failed: {e}')
            messages.success(request, 'Your message has been sent. We\'ll get back to you soon!')
            return redirect('shop:contact')
    return render(request, 'shop/contact.html', {'form': form})


def faq(request):
    return render(request, 'shop/faq.html')


def privacy(request):
    return render(request, 'shop/privacy.html')


def terms(request):
    return render(request, 'shop/terms.html')


def shipping_policy(request):
    return render(request, 'shop/shipping_policy.html')


def returns_policy(request):
    return render(request, 'shop/returns_policy.html')

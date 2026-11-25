import uuid
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg
from django.shortcuts import reverse
from django.utils import timezone


def validate_storefront_url(value):
    value = value.strip()
    if not value:
        return

    parsed = urlsplit(value)
    if parsed.scheme in ('http', 'https'):
        if not parsed.netloc:
            raise ValidationError('Enter a valid website URL.')
    elif parsed.scheme in ('mailto', 'tel'):
        if not parsed.path:
            raise ValidationError('Enter a valid contact URL.')
    elif parsed.scheme or parsed.netloc or value.startswith('//'):
        raise ValidationError('Use a relative path, http(s), mailto, or tel URL.')


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('shop:product_list') + f'?category={self.slug}'


class SubCategory(models.Model):
    category = models.ForeignKey(Category, related_name='subcategories', on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)

    class Meta:
        unique_together = ('category', 'slug')
        verbose_name_plural = 'Subcategories'

    def __str__(self):
        return f'{self.category.name} / {self.name}'


class Brand(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    CURRENCY_CHOICES = [
        ('BDT', 'Bangladeshi Taka'),
        ('USD', 'US Dollar'),
    ]

    name = models.CharField(max_length=250)
    slug = models.SlugField(max_length=260, unique=True)
    sku = models.CharField(max_length=80, unique=True)
    brand = models.ForeignKey(Brand, related_name='products', on_delete=models.SET_NULL, null=True, blank=True)
    category = models.ForeignKey(Category, related_name='products', on_delete=models.SET_NULL, null=True)
    subcategory = models.ForeignKey(SubCategory, related_name='products', on_delete=models.SET_NULL, null=True, blank=True)
    tags = models.ManyToManyField(Tag, related_name='products', blank=True)
    description = models.TextField(blank=True)
    short_description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='BDT')
    price_on_request = models.BooleanField(default=False)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)
    featured = models.BooleanField(default=False)
    published = models.BooleanField(default=True)
    draft = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('shop:product_detail', args=[self.slug])

    @property
    def price_display(self):
        return self.sale_price if self.sale_price else self.price

    @property
    def is_digital_service(self):
        return bool(self.category_id and self.category.slug == 'digital-services')

    @property
    def is_in_stock(self):
        if self.is_digital_service:
            return True
        variants = self.variants.all()
        if variants.exists():
            return variants.filter(stock__gt=0).exists()
        return self.stock > 0

    def average_rating(self):
        return self.reviews.filter(approved=True).aggregate(Avg('rating'))['rating__avg'] or 0

    @property
    def primary_image(self):
        return self.images.filter(is_primary=True).first() or self.images.first()

    @property
    def featured_image(self):
        return self.images.filter(is_featured=True).first() or self.primary_image


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, related_name='variants', on_delete=models.CASCADE)
    name = models.CharField(max_length=80)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='products/variants/', blank=True, null=True)

    class Meta:
        unique_together = ('product', 'name')
        ordering = ['price']

    def __str__(self):
        return f'{self.product.name} - {self.name}'

    @property
    def price_display(self):
        return self.sale_price if self.sale_price else self.price

    @property
    def is_in_stock(self):
        return self.stock > 0


class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='products/')
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)

    def __str__(self):
        return f'Image for {self.product.name}'


class ProductSpecification(models.Model):
    product = models.ForeignKey(Product, related_name='specifications', on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    value = models.CharField(max_length=250)

    def __str__(self):
        return f'{self.name}: {self.value}'


class Review(models.Model):
    product = models.ForeignKey(Product, related_name='reviews', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='reviews', on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=120, blank=True)
    comment = models.TextField()
    approved = models.BooleanField(default=True)
    verified_purchase = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.rating} stars by {self.user.username}'


class Question(models.Model):
    product = models.ForeignKey(Product, related_name='questions', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='questions', on_delete=models.CASCADE)
    question = models.TextField()
    answer = models.TextField(blank=True)
    asked_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'Q for {self.product.name}'


class Coupon(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed amount'),
    ]
    code = models.CharField(max_length=60, unique=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    active = models.BooleanField(default=True)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    usage_limit = models.PositiveIntegerField(default=100)
    used_count = models.PositiveIntegerField(default=0)
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return self.code

    def is_valid(self):
        now = timezone.now()
        return self.active and self.valid_from <= now <= self.valid_to and self.used_count < self.usage_limit

    def discount_value(self, total):
        if self.discount_type == 'percentage':
            return min(total * (self.amount / 100), total)
        return min(self.amount, total)


class Address(models.Model):
    ADDRESS_TYPE = [('shipping', 'Shipping'), ('billing', 'Billing')]
    user = models.ForeignKey(User, related_name='addresses', on_delete=models.CASCADE)
    label = models.CharField(max_length=120, default='Home')
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=40)
    country = models.CharField(max_length=100, default='Bangladesh')
    phone = models.CharField(max_length=40)
    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPE, default='shipping')
    default = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.label} - {self.city}'


def generate_order_number():
    """Generate a unique order number like RF-20261004-ABC1"""
    import random
    import string
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    date_str = timezone.now().strftime('%Y%m%d')
    return f'RF-{date_str}-{suffix}'


class Order(models.Model):
    CURRENCY_CHOICES = Product.CURRENCY_CHOICES

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('packed', 'Packed'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
        ('refunded', 'Refunded'),
    ]
    # user is optional for guest orders
    user = models.ForeignKey(User, related_name='orders', on_delete=models.SET_NULL, null=True, blank=True)
    # Unique human-readable order number
    order_number = models.CharField(max_length=30, unique=True, blank=True)
    # Guest session tracking
    session_key = models.CharField(max_length=40, blank=True)
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40)
    shipping_address = models.CharField(max_length=255)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100, blank=True)
    shipping_postal_code = models.CharField(max_length=40, blank=True)
    shipping_country = models.CharField(max_length=100, default='Bangladesh')
    billing_address = models.CharField(max_length=255, blank=True)
    billing_city = models.CharField(max_length=100, blank=True)
    billing_state = models.CharField(max_length=100, blank=True)
    billing_postal_code = models.CharField(max_length=40, blank=True)
    billing_country = models.CharField(max_length=100, blank=True)
    note = models.TextField(blank=True)
    coupon = models.ForeignKey(Coupon, null=True, blank=True, on_delete=models.SET_NULL)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='BDT')
    requires_quote = models.BooleanField(default=False)
    payment_method = models.CharField(max_length=50, default='Cash on Delivery')
    payment_status = models.CharField(max_length=60, default='Pending')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    is_new = models.BooleanField(default=True)  # For admin "new order" indicator
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        name = self.user.username if self.user else f'{self.first_name} {self.last_name}'
        return f'Order {self.order_number} - {name}'

    def save(self, *args, **kwargs):
        if not self.order_number:
            # Generate unique order number
            while True:
                num = generate_order_number()
                if not Order.objects.filter(order_number=num).exists():
                    self.order_number = num
                    break
        super().save(*args, **kwargs)

    def get_subtotal(self):
        return sum(item.total_price() for item in self.items.all())

    def get_discounted_total(self):
        return max(self.total - self.discount, 0)

    @property
    def quote_only(self):
        return self.requires_quote and self.total == 0

    def can_cancel(self):
        return self.status in ['pending', 'confirmed', 'processing']


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name='order_items', on_delete=models.SET_NULL, null=True)
    variant = models.ForeignKey(ProductVariant, related_name='order_items', on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=250, blank=True)  # Snapshot at time of order
    variant_name = models.CharField(max_length=80, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def total_price(self):
        return self.quantity * self.unit_price

    @property
    def total_price_property(self):
        return self.quantity * self.unit_price

    def __str__(self):
        name = self.product_name or (self.product.name if self.product else 'Unknown')
        return f'{self.quantity} x {name}'


class WishlistItem(models.Model):
    user = models.ForeignKey(User, related_name='wishlist_items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name='wishlisted', on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f'{self.product.name} in {self.user.username} wishlist'


class CartItem(models.Model):
    user = models.ForeignKey(User, related_name='cart_items', on_delete=models.CASCADE, null=True, blank=True)
    session_id = models.CharField(max_length=255, blank=True, null=True)
    product = models.ForeignKey(Product, related_name='cart_items', on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, related_name='cart_items', on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product', 'variant', 'session_id')

    def __str__(self):
        return f'{self.quantity} x {self.product.name}'

    def total_price(self):
        price = self.variant.price_display if self.variant else self.product.price_display
        return self.quantity * price


class UserProfile(models.Model):
    user = models.OneToOneField(User, related_name='profile', on_delete=models.CASCADE)
    phone = models.CharField(max_length=40, blank=True)
    email_verified = models.BooleanField(default=False)
    newsletter = models.BooleanField(default=True)

    def __str__(self):
        return self.user.username


class StorefrontContent(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    brand_name = models.CharField(max_length=100, default='Bdcrafter')
    brand_suffix = models.CharField(max_length=20, default='.com')
    brand_url = models.CharField(max_length=500, default='/', validators=[validate_storefront_url])

    hero_eyebrow = models.CharField(max_length=180, default='HANDMADE • TECH • DIGITAL • DHAKA')
    hero_background_url = models.CharField(
        max_length=500,
        default='https://images.unsplash.com/photo-1499951360447-b19be8fe80f5?auto=format&fit=crop&w=1400&q=80',
        validators=[validate_storefront_url],
    )
    hero_title_lead = models.CharField(max_length=120, default='Craft worth')
    hero_title_emphasis = models.CharField(max_length=80, default='owning')
    hero_description_prefix = models.TextField(
        default='Handmade kushikata, smart gadgets, digital services, tailored clothes, botanical perfumes, and organic goods — curated under one roof at '
    )
    hero_brand_text = models.CharField(max_length=120, default='bdcrafter.com')
    hero_description_suffix = models.CharField(max_length=120, default='.')
    hero_primary_label = models.CharField(max_length=80, default='Explore Store')
    hero_primary_url = models.CharField(max_length=500, default='/products/', validators=[validate_storefront_url])
    hero_secondary_label = models.CharField(max_length=80, default='Book a Service')
    hero_secondary_url = models.CharField(max_length=500, default='/contact/', validators=[validate_storefront_url])

    hero_card_eyebrow = models.CharField(max_length=80, default='The Bdcrafter edit')
    hero_card_title_lead = models.CharField(max_length=80, default='Good finds,')
    hero_card_title_emphasis = models.CharField(max_length=80, default='all in one place.')
    hero_card_tag_one = models.CharField(max_length=40, default='Handmade')
    hero_card_tag_two = models.CharField(max_length=40, default='Everyday tech')
    hero_card_tag_three = models.CharField(max_length=40, default='Organic')
    hero_card_footer = models.CharField(max_length=80, default='Curated for everyday')

    hero_stat_one_value = models.CharField(max_length=30, default='6')
    hero_stat_one_label = models.CharField(max_length=50, default='Categories')
    hero_stat_two_value = models.CharField(max_length=30, default='Free')
    hero_stat_two_label = models.CharField(max_length=50, default='Delivery')
    hero_stat_three_value = models.CharField(max_length=30, default='4.9')
    hero_stat_three_label = models.CharField(max_length=50, default='Rating')

    home_category_heading = models.CharField(max_length=120, default='Shop by Category')
    home_category_link_label = models.CharField(max_length=80, default='View all')
    home_category_link_url = models.CharField(max_length=500, default='/products/', validators=[validate_storefront_url])
    home_featured_heading = models.CharField(max_length=120, default='Featured Products')
    home_featured_link_label = models.CharField(max_length=80, default='View all')
    home_featured_link_url = models.CharField(max_length=500, default='/products/', validators=[validate_storefront_url])
    home_arrivals_heading = models.CharField(max_length=120, default='New Arrivals')
    home_arrivals_link_label = models.CharField(max_length=80, default='View all')
    home_arrivals_link_url = models.CharField(max_length=500, default='/products/?sort=newest', validators=[validate_storefront_url])
    home_product_view_label = models.CharField(max_length=40, default='View')
    home_product_new_badge = models.CharField(max_length=40, default='New')
    home_product_sale_badge = models.CharField(max_length=40, default='Sale')

    home_cta_eyebrow = models.CharField(max_length=160, default="Bangladesh's Curated Marketplace")
    home_cta_title = models.CharField(max_length=180, default='Shopping made easy with Bdcrafter.com')
    home_cta_description = models.TextField(
        default='Browse our six curated categories to discover products and services for everyday life in Bangladesh.'
    )
    home_cta_button_label = models.CharField(max_length=80, default='Browse All Products')
    home_cta_button_url = models.CharField(max_length=500, default='/products/', validators=[validate_storefront_url])
    home_cta_background_url = models.CharField(
        max_length=500,
        default='/media/products/category-samples/cushion.jpg',
        validators=[validate_storefront_url],
    )

    footer_brand_description = models.TextField(
        default='Handmade kushikata, smart gadgets, digital services, tailored clothes, botanical perfumes, and organic goods — curated under one roof from Dhaka.'
    )
    footer_quick_links_heading = models.CharField(max_length=80, default='Quick Links')
    footer_policies_heading = models.CharField(max_length=80, default='Policies')
    footer_contact_heading = models.CharField(max_length=80, default='Contact')
    footer_address_text = models.CharField(max_length=180, default='Dhaka, Bangladesh')
    footer_address_url = models.CharField(max_length=500, blank=True, validators=[validate_storefront_url])
    footer_phone_text = models.CharField(max_length=80, default='+880 1234 567890')
    footer_phone_url = models.CharField(max_length=500, default='tel:+8801234567890', validators=[validate_storefront_url])
    footer_email_text = models.CharField(max_length=120, default='support@bdcrafter.com')
    footer_email_url = models.CharField(max_length=500, default='mailto:support@bdcrafter.com', validators=[validate_storefront_url])
    footer_whatsapp_text = models.CharField(max_length=80, default='WhatsApp Us')
    footer_whatsapp_url = models.CharField(max_length=500, default='https://wa.me/8801234567890', validators=[validate_storefront_url])
    footer_facebook_label = models.CharField(max_length=80, default='Facebook')
    footer_facebook_url = models.CharField(max_length=500, default='#', validators=[validate_storefront_url])
    footer_instagram_label = models.CharField(max_length=80, default='Instagram')
    footer_instagram_url = models.CharField(max_length=500, default='#', validators=[validate_storefront_url])
    footer_country_text = models.CharField(max_length=120, default='Made in Bangladesh')
    footer_copyright_text = models.CharField(max_length=160, default='All rights reserved.')

    class Meta:
        verbose_name = 'Homepage and footer content'
        verbose_name_plural = 'Homepage and footer content'

    def __str__(self):
        return 'Homepage and footer content'


class HeaderNavigationLink(models.Model):
    PLACEMENT_CHOICES = [
        ('both', 'Desktop and mobile'),
        ('desktop', 'Desktop only'),
        ('mobile', 'Mobile only'),
    ]
    content = models.ForeignKey(StorefrontContent, related_name='header_links', on_delete=models.CASCADE)
    label = models.CharField(max_length=80)
    url = models.CharField(max_length=500, validators=[validate_storefront_url])
    placement = models.CharField(max_length=10, choices=PLACEMENT_CHOICES, default='both')
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = 'Header navigation link'
        verbose_name_plural = 'Header navigation links'

    def __str__(self):
        return self.label


class FooterNavigationLink(models.Model):
    SECTION_CHOICES = [
        ('quick', 'Quick links'),
        ('policy', 'Policies'),
    ]
    content = models.ForeignKey(StorefrontContent, related_name='footer_links', on_delete=models.CASCADE)
    section = models.CharField(max_length=12, choices=SECTION_CHOICES)
    label = models.CharField(max_length=80)
    url = models.CharField(max_length=500, validators=[validate_storefront_url])
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['section', 'sort_order', 'id']
        verbose_name = 'Footer navigation link'
        verbose_name_plural = 'Footer navigation links'

    def __str__(self):
        return self.label


class HomepageTrustFeature(models.Model):
    ICON_CHOICES = [
        ('truck', 'Delivery truck'),
        ('wallet', 'Payment'),
        ('check-circle', 'Quality check'),
        ('rotate', 'Returns'),
        ('shield', 'Security'),
    ]
    content = models.ForeignKey(StorefrontContent, related_name='trust_features', on_delete=models.CASCADE)
    icon = models.CharField(max_length=20, choices=ICON_CHOICES, default='check-circle')
    title = models.CharField(max_length=80)
    description = models.CharField(max_length=180)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = 'Homepage trust feature'
        verbose_name_plural = 'Homepage trust features'

    def __str__(self):
        return self.title

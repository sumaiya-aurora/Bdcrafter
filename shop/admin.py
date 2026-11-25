from django.contrib import admin
from .models import (
    Category,
    SubCategory,
    Brand,
    Tag,
    Product,
    ProductVariant,
    ProductImage,
    ProductSpecification,
    Review,
    Question,
    Coupon,
    Address,
    Order,
    OrderItem,
    WishlistItem,
    CartItem,
    UserProfile,
    StorefrontContent,
    HeaderNavigationLink,
    FooterNavigationLink,
    HomepageTrustFeature,
)
from .context_processors import STORE_CATEGORY_SLUGS

admin.site.site_header = 'Bdcrafter.com Administration'
admin.site.site_title = 'Bdcrafter.com Admin'
admin.site.index_title = 'Store Management'


class StoreCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'description')
    search_fields = ('name', 'slug')

    def get_queryset(self, request):
        return super().get_queryset(request).filter(slug__in=STORE_CATEGORY_SLUGS)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductSpecificationInline(admin.TabularInline):
    model = ProductSpecification
    extra = 1


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 3


class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'sku', 'brand', 'category', 'subcategory', 'price', 'currency',
        'price_on_request', 'stock', 'featured', 'published',
    )
    list_filter = ('brand', 'category', 'subcategory', 'currency', 'price_on_request', 'featured', 'published', 'draft')
    search_fields = ('name', 'sku', 'description')
    inlines = [ProductVariantInline, ProductImageInline, ProductSpecificationInline]
    prepopulated_fields = {'slug': ('name',)}

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'category':
            kwargs['queryset'] = Category.objects.filter(slug__in=STORE_CATEGORY_SLUGS)
        if db_field.name == 'subcategory':
            kwargs['queryset'] = SubCategory.objects.filter(
                category__slug__in=STORE_CATEGORY_SLUGS
            ).select_related('category').order_by('category__name', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    readonly_fields = ('product', 'quantity', 'unit_price')
    extra = 0


class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'payment_method', 'display_total', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('user__username', 'id', 'email')
    inlines = [OrderItemInline]
    actions = ['mark_packed', 'mark_shipped', 'mark_delivered']

    @admin.display(description='Total')
    def display_total(self, order):
        if order.quote_only:
            return 'Quote pending'
        quote_note = ' + quote pending' if order.requires_quote else ''
        return f'{order.currency} {order.total}{quote_note}'

    def mark_packed(self, request, queryset):
        queryset.update(status='packed')

    def mark_shipped(self, request, queryset):
        queryset.update(status='shipped')

    def mark_delivered(self, request, queryset):
        queryset.update(status='delivered')

    mark_packed.short_description = 'Mark selected orders as Packed'
    mark_shipped.short_description = 'Mark selected orders as Shipped'
    mark_delivered.short_description = 'Mark selected orders as Delivered'


class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'amount', 'active', 'valid_from', 'valid_to', 'used_count')
    search_fields = ('code',)


class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'added_at')
    search_fields = ('user__username', 'product__name')


class CartItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'session_id', 'product', 'quantity', 'added_at')
    search_fields = ('user__username', 'product__name', 'session_id')


class HeaderNavigationLinkInline(admin.TabularInline):
    model = HeaderNavigationLink
    extra = 0
    fields = ('label', 'url', 'placement', 'sort_order', 'is_active')


class FooterNavigationLinkInline(admin.TabularInline):
    model = FooterNavigationLink
    extra = 0
    fields = ('section', 'label', 'url', 'sort_order', 'is_active')


class HomepageTrustFeatureInline(admin.TabularInline):
    model = HomepageTrustFeature
    extra = 0
    fields = ('icon', 'title', 'description', 'sort_order', 'is_active')


@admin.register(StorefrontContent)
class StorefrontContentAdmin(admin.ModelAdmin):
    list_display = ('brand_name',)
    inlines = [
        HeaderNavigationLinkInline,
        FooterNavigationLinkInline,
        HomepageTrustFeatureInline,
    ]
    fieldsets = [
        ('Brand', {
            'fields': (('brand_name', 'brand_suffix'), 'brand_url'),
        }),
        ('Homepage hero', {
            'fields': (
                'hero_eyebrow', 'hero_background_url',
                ('hero_title_lead', 'hero_title_emphasis'),
                'hero_description_prefix',
                ('hero_brand_text', 'hero_description_suffix'),
                ('hero_primary_label', 'hero_primary_url'),
                ('hero_secondary_label', 'hero_secondary_url'),
            ),
        }),
        ('Hero side card copy', {
            'fields': (
                'hero_card_eyebrow',
                ('hero_card_title_lead', 'hero_card_title_emphasis'),
                ('hero_card_tag_one', 'hero_card_tag_two', 'hero_card_tag_three'),
                'hero_card_footer',
            ),
        }),
        ('Homepage sections', {
            'fields': (
                ('home_category_heading', 'home_category_link_label', 'home_category_link_url'),
                ('home_featured_heading', 'home_featured_link_label', 'home_featured_link_url'),
                ('home_arrivals_heading', 'home_arrivals_link_label', 'home_arrivals_link_url'),
                ('home_product_view_label', 'home_product_new_badge', 'home_product_sale_badge'),
            ),
        }),
        ('Homepage call to action', {
            'fields': (
                'home_cta_eyebrow', 'home_cta_title', 'home_cta_description',
                ('home_cta_button_label', 'home_cta_button_url'),
                'home_cta_background_url',
            ),
        }),
        ('Footer copy', {
            'fields': (
                'footer_brand_description',
                ('footer_quick_links_heading', 'footer_policies_heading', 'footer_contact_heading'),
                ('footer_country_text', 'footer_copyright_text'),
            ),
        }),
        ('Footer contact details', {
            'fields': (
                ('footer_address_text', 'footer_address_url'),
                ('footer_phone_text', 'footer_phone_url'),
                ('footer_email_text', 'footer_email_url'),
                ('footer_whatsapp_text', 'footer_whatsapp_url'),
                ('footer_facebook_label', 'footer_facebook_url'),
                ('footer_instagram_label', 'footer_instagram_url'),
            ),
        }),
    ]

    def has_add_permission(self, request):
        return not StorefrontContent.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Category, StoreCategoryAdmin)
admin.site.register(SubCategory)
admin.site.register(Brand)
admin.site.register(Tag)
admin.site.register(Product, ProductAdmin)
admin.site.register(Review)
admin.site.register(Question)
admin.site.register(Coupon, CouponAdmin)
admin.site.register(Address)
admin.site.register(Order, OrderAdmin)
admin.site.register(WishlistItem, WishlistAdmin)
admin.site.register(CartItem, CartItemAdmin)
admin.site.register(UserProfile)

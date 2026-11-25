from decimal import Decimal

from django.db import migrations


PORTFOLIO_DESCRIPTION = (
    'Standard package — $100 USD\n'
    '• Up to 5 pages\n'
    '• Responsive layout for mobile, tablet, and desktop\n'
    '• Contact form and clear calls to action\n'
    '• Basic on-page SEO setup\n'
    '• Website handover'
)
ECOMMERCE_DESCRIPTION = (
    'Standard package — $300 USD\n'
    '• Storefront with responsive product and category pages\n'
    '• Setup for up to 20 products\n'
    '• Cart and checkout setup\n'
    '• Basic on-page SEO setup\n'
    '• Website handover'
)
LANDING_DESCRIPTION = (
    'Standard package — $150 USD\n'
    '• One responsive landing page\n'
    '• Contact section and clear calls to action\n'
    '• Basic on-page SEO setup\n'
    '• Page handover'
)
CUSTOM_DESCRIPTION = (
    'Custom Digital Service — price upon discussion.\n'
    'Services can include recharge assistant support, virtual assistance, data entry, '
    'web research, and other agreed digital tasks.\n'
    'Typical rate: $30-$45 USD per hour. The hourly range is informational and is not '
    'included in the order total. Final scope, hours, and price will be agreed after '
    'the order is received.'
)
SOCIAL_DESIGN_DESCRIPTION = (
    'Standard social media design package with brand-aligned creative assets, '
    'platform-ready exports, and file handover. The number of designs and final scope '
    'are agreed before work begins. Price upon discussion.'
)
LEGACY_WEBSITE_DESCRIPTION = (
    'Standard portfolio website package for small businesses. Includes up to 5 pages, '
    'a responsive layout, contact form, basic on-page SEO, and website handover. '
    'Price: $100 USD.'
)


def seed_digital_service_packages(apps, schema_editor):
    Category = apps.get_model('shop', 'Category')
    Product = apps.get_model('shop', 'Product')
    ProductImage = apps.get_model('shop', 'ProductImage')

    category = Category.objects.get(slug='digital-services')
    source_image = ProductImage.objects.filter(
        product__category=category,
        is_primary=True,
    ).first()

    def ensure_service_image(product):
        if source_image and not ProductImage.objects.filter(product=product, is_primary=True).exists():
            ProductImage.objects.create(
                product=product,
                image=source_image.image.name,
                alt_text=product.name,
                is_primary=True,
                is_featured=True,
            )

    legacy_website = Product.objects.filter(
        sku='BDC-DIG-001',
        category=category,
        name='Basic Business Website Setup',
        description=(
            'A website setup service for small businesses. Review the listing for '
            'project scope, price, and service details before ordering.'
        ),
    ).first()
    if legacy_website:
        legacy_website.name = 'Portfolio Website'
        legacy_website.short_description = (
            'Up to 5 pages, responsive layout, contact form, basic SEO, and handover.'
        )
        legacy_website.description = LEGACY_WEBSITE_DESCRIPTION
        legacy_website.price = Decimal('100.00')
        legacy_website.currency = 'USD'
        legacy_website.price_on_request = False
        legacy_website.save(update_fields=[
            'name', 'short_description', 'description', 'price',
            'currency', 'price_on_request',
        ])
        ProductImage.objects.filter(
            product=legacy_website,
            alt_text='Basic Business Website Setup',
        ).update(alt_text='Portfolio Website')
    else:
        portfolio, _ = Product.objects.get_or_create(
            sku='BDC-DIG-006',
            defaults={
                'name': 'Portfolio Website',
                'slug': 'portfolio-website',
                'category': category,
                'price': Decimal('100.00'),
                'currency': 'USD',
                'price_on_request': False,
                'stock': 10000,
                'short_description': (
                    'Up to 5 pages, responsive layout, contact form, basic SEO, and handover.'
                ),
                'description': LEGACY_WEBSITE_DESCRIPTION,
                'published': True,
                'draft': False,
                'featured': False,
            },
        )
        ensure_service_image(portfolio)

    social_design = Product.objects.filter(
        sku='BDC-DIG-002',
        category=category,
        name='Social Media Design Starter Pack',
        description=(
            'A starter package for social media design. Review the listing for service '
            'details, price, and availability before ordering.'
        ),
    ).first()
    if social_design:
        social_design.short_description = (
            'Brand-aligned social media creative assets with platform-ready exports.'
        )
        social_design.description = SOCIAL_DESIGN_DESCRIPTION
        social_design.price = Decimal('0.00')
        social_design.currency = 'USD'
        social_design.price_on_request = True
        social_design.save(update_fields=[
            'short_description', 'description', 'price', 'currency',
            'price_on_request',
        ])

    packages = [
        {
            'name': 'Ecommerce Site',
            'slug': 'ecommerce-site',
            'sku': 'BDC-DIG-003',
            'price': Decimal('300.00'),
            'short_description': (
                'Responsive storefront with setup for up to 20 products, cart, '
                'checkout, basic SEO, and handover.'
            ),
            'description': ECOMMERCE_DESCRIPTION,
            'price_on_request': False,
        },
        {
            'name': 'Landing Page',
            'slug': 'landing-page',
            'sku': 'BDC-DIG-004',
            'price': Decimal('150.00'),
            'short_description': (
                'One responsive page with contact and call-to-action sections, '
                'basic SEO, and handover.'
            ),
            'description': LANDING_DESCRIPTION,
            'price_on_request': False,
        },
        {
            'name': 'Custom Digital Service',
            'slug': 'custom-digital-service',
            'sku': 'BDC-DIG-005',
            'price': Decimal('0.00'),
            'short_description': (
                'Recharge assistant, virtual assistant, and other custom digital tasks.'
            ),
            'description': CUSTOM_DESCRIPTION,
            'price_on_request': True,
        },
    ]

    for package in packages:
        product, _ = Product.objects.get_or_create(
            sku=package['sku'],
            defaults={
                **package,
                'category': category,
                'currency': 'USD',
                'stock': 10000,
                'published': True,
                'draft': False,
                'featured': False,
            },
        )
        ensure_service_image(product)


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0013_order_currency_order_requires_quote_product_currency_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_digital_service_packages, migrations.RunPython.noop),
    ]

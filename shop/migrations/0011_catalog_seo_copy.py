from django.db import migrations


OLD_CATEGORY_DESCRIPTIONS = {
    'kushikata': 'Kushikata and traditional hand-crafted goods.',
    'gadgets': 'Gadgets and consumer electronics.',
    'digital-services': 'Digital products and services.',
    'clothes': 'Clothing and fashion.',
    'perfume': 'Perfumes and fragrances.',
    'organic-store': 'Organic foods and natural products.',
}

CATEGORY_DESCRIPTIONS = {
    'kushikata': (
        'Browse handcrafted kushikata and home-textile pieces, including kantha cushion covers. '
        'Review each listing for product details, price, and current availability.'
    ),
    'gadgets': (
        'Shop everyday gadgets and accessories, including wireless earbuds and USB-C chargers. '
        'Compare product details, prices, and current stock before ordering.'
    ),
    'digital-services': (
        'Explore digital services such as website setup and social media design packages. '
        'Review each listing for scope, price, and service details before ordering.'
    ),
    'clothes': (
        'Browse everyday clothing, including cotton kurtis and panjabis. '
        'Check each product listing for details, price, and current availability.'
    ),
    'perfume': (
        'Explore perfumes and attar across a range of fragrance collections. '
        'Review individual listings for fragrance details, price, and availability.'
    ),
    'organic-store': (
        'Browse pantry and natural-product listings, including forest honey and cold-pressed mustard oil. '
        'Check product details, price, and current availability before ordering.'
    ),
}

PRODUCT_COPY = {
    'bdc-org-002': (
        'Cold-pressed mustard oil in a 1 L bottle.',
        'Cold-pressed mustard oil in a 1 L bottle. Check the listing for current price, product details, and availability before ordering.',
    ),
    'bdc-org-001': (
        'Forest honey in a 500 g pack.',
        'Forest honey in a 500 g pack. Check the listing for current price, product details, and availability before ordering.',
    ),
    'bdc-clo-002': (
        'Everyday cotton kurti.',
        'An everyday cotton kurti. Review the listing for product details, price, and current stock before ordering.',
    ),
    'bdc-clo-001': (
        'Classic cotton panjabi.',
        'A classic cotton panjabi. Review the listing for product details, price, and current stock before ordering.',
    ),
    'bdc-dig-002': (
        'Starter package for social media design.',
        'A starter package for social media design. Review the listing for service details, price, and availability before ordering.',
    ),
    'bdc-dig-001': (
        'Website setup service for small businesses.',
        'A website setup service for small businesses. Review the listing for project scope, price, and service details before ordering.',
    ),
    'bdc-gad-002': (
        '20W USB-C fast charger.',
        'A 20W USB-C fast charger. Review the listing for product details, compatibility information, price, and current availability.',
    ),
    'bdc-gad-001': (
        'Wireless Bluetooth earbuds.',
        'Wireless Bluetooth earbuds. Review the listing for product details, compatibility information, price, and current availability.',
    ),
    'bdc-kus-002': (
        'Handwoven jute storage basket.',
        'A handwoven jute storage basket for home organization. Check the listing for product details, price, and availability.',
    ),
    'bdc-kus-001': (
        'Nakshi kantha cushion cover.',
        'A Nakshi kantha cushion cover. Review the listing for product details, price, and current availability before ordering.',
    ),
}

PLACEHOLDER_DESCRIPTION = (
    'Sample catalog listing. Verify product specifications, final price, and availability before fulfillment.'
)
PLACEHOLDER_SHORT_DESCRIPTION = 'Sample listing for review.'


def update_catalog_copy(apps, schema_editor):
    database = schema_editor.connection.alias
    Category = apps.get_model('shop', 'Category')
    Product = apps.get_model('shop', 'Product')

    for slug, description in CATEGORY_DESCRIPTIONS.items():
        category = Category.objects.using(database).filter(slug=slug).first()
        if category and category.description in ('', OLD_CATEGORY_DESCRIPTIONS[slug]):
            category.description = description
            category.save(using=database, update_fields=['description'])

    for slug, (short_description, description) in PRODUCT_COPY.items():
        Product.objects.using(database).filter(
            slug=slug,
            short_description=PLACEHOLDER_SHORT_DESCRIPTION,
            description=PLACEHOLDER_DESCRIPTION,
        ).update(
            short_description=short_description,
            description=description,
        )


class Migration(migrations.Migration):
    dependencies = [
        ('shop', '0010_storefrontcontent_homepagetrustfeature_and_more'),
    ]

    operations = [
        migrations.RunPython(update_catalog_copy, migrations.RunPython.noop),
    ]

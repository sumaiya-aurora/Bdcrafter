from django.db import migrations


SAMPLE_PRODUCTS = [
    ('kushikata', 'Nakshi Kantha Cushion Cover', 'BDC-KUS-001', '850.00', 5, True),
    ('kushikata', 'Handwoven Jute Storage Basket', 'BDC-KUS-002', '650.00', 5, False),
    ('gadgets', 'Wireless Bluetooth Earbuds', 'BDC-GAD-001', '1290.00', 5, True),
    ('gadgets', '20W USB-C Fast Charger', 'BDC-GAD-002', '790.00', 5, False),
    ('digital-services', 'Basic Business Website Setup', 'BDC-DIG-001', '5000.00', 5, True),
    ('digital-services', 'Social Media Design Starter Pack', 'BDC-DIG-002', '1500.00', 5, False),
    ('clothes', 'Classic Cotton Panjabi', 'BDC-CLO-001', '1490.00', 5, True),
    ('clothes', 'Everyday Cotton Kurti', 'BDC-CLO-002', '1290.00', 5, False),
    ('organic-store', 'Raw Forest Honey 500g', 'BDC-ORG-001', '650.00', 5, True),
    ('organic-store', 'Cold-Pressed Mustard Oil 1L', 'BDC-ORG-002', '480.00', 5, False),
]


def create_sample_products(apps, schema_editor):
    Category = apps.get_model('shop', 'Category')
    Product = apps.get_model('shop', 'Product')
    database = schema_editor.connection.alias

    for category_slug, name, sku, price, stock, featured in SAMPLE_PRODUCTS:
        category = Category.objects.using(database).get(slug=category_slug)
        Product.objects.using(database).get_or_create(
            sku=sku,
            defaults={
                'name': name,
                'slug': sku.lower(),
                'category': category,
                'description': (
                    'Sample catalog listing. Verify product specifications, '
                    'final price, and availability before fulfillment.'
                ),
                'short_description': 'Sample listing for review.',
                'price': price,
                'stock': stock,
                'published': True,
                'featured': featured,
                'draft': False,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ('shop', '0005_bdcrafter_categories'),
    ]

    operations = [
        migrations.RunPython(create_sample_products, migrations.RunPython.noop),
    ]

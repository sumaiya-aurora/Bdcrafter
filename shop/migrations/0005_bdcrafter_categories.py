from django.db import migrations


CATEGORIES = [
    ('Kushikata', 'kushikata', 'Kushikata and traditional hand-crafted goods.'),
    ('Gadgets', 'gadgets', 'Gadgets and consumer electronics.'),
    ('Digital Services', 'digital-services', 'Digital products and services.'),
    ('Clothes', 'clothes', 'Clothing and fashion.'),
    ('Perfume', 'perfume', 'Perfumes and fragrances.'),
    ('Organic Store', 'organic-store', 'Organic foods and natural products.'),
]

LEGACY_PERFUME_CATEGORY_SLUGS = [
    'casual-scents',
    'elite-section',
    'high-end',
    'elegant-collection',
]


def create_store_categories(apps, schema_editor):
    Category = apps.get_model('shop', 'Category')
    Product = apps.get_model('shop', 'Product')
    database = schema_editor.connection.alias

    for name, slug, description in CATEGORIES:
        Category.objects.using(database).get_or_create(
            slug=slug,
            defaults={'name': name, 'description': description},
        )

    perfume = Category.objects.using(database).get(slug='perfume')
    Product.objects.using(database).filter(
        category__slug__in=LEGACY_PERFUME_CATEGORY_SLUGS,
    ).update(category=perfume)


class Migration(migrations.Migration):
    dependencies = [
        ('shop', '0004_productimage_is_featured_productvariant_image'),
    ]

    operations = [
        migrations.RunPython(create_store_categories, migrations.RunPython.noop),
    ]

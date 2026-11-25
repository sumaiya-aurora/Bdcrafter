from django.db import migrations
from django.utils.text import slugify


CATEGORY_SUBCATEGORIES = {
    'kushikata': ['Traditional', 'Handicrafts', 'Textiles'],
    'gadgets': ['Mobile Accessories', 'Audio', 'Power & Charging'],
    'digital-services': ['Website Services', 'Design Services', 'Marketing Services'],
    'clothes': ['Men', 'Women', 'Accessories'],
    'perfume': ['Casual Scents', 'Elite Section', 'High-End', 'Elegant Collection'],
    'organic-store': ['Organic Food', 'Organic Oils', 'Natural Care'],
}


def create_subcategories(apps, schema_editor):
    Category = apps.get_model('shop', 'Category')
    SubCategory = apps.get_model('shop', 'SubCategory')
    Product = apps.get_model('shop', 'Product')
    database = schema_editor.connection.alias

    subcategories = {}
    for category_slug, names in CATEGORY_SUBCATEGORIES.items():
        category = Category.objects.using(database).filter(slug=category_slug).first()
        if not category:
            continue
        for name in names:
            subcategory, _ = SubCategory.objects.using(database).get_or_create(
                category=category,
                slug=slugify(name),
                defaults={'name': name},
            )
            subcategories[(category_slug, slugify(name))] = subcategory

    perfume_slug_map = {
        'casual-scents': 'casual-scents',
        'elite-section': 'elite-section',
        'high-end': 'high-end',
        'elegant-collection': 'elegant-collection',
    }
    perfume = Category.objects.using(database).filter(slug='perfume').first()
    if perfume:
        for prefix, subcategory_slug in perfume_slug_map.items():
            subcategory = subcategories[('perfume', subcategory_slug)]
            Product.objects.using(database).filter(
                category=perfume,
                slug__startswith=f'{prefix}-',
            ).update(subcategory=subcategory)

    sample_subcategory_map = {
        'bdc-kus': ('kushikata', 'traditional'),
        'bdc-gad': ('gadgets', 'mobile-accessories'),
        'bdc-dig': ('digital-services', 'website-services'),
        'bdc-clo': ('clothes', 'men'),
        'bdc-org': ('organic-store', 'organic-food'),
    }
    for sku_prefix, (category_slug, subcategory_slug) in sample_subcategory_map.items():
        subcategory = subcategories[(category_slug, subcategory_slug)]
        Product.objects.using(database).filter(
            sku__startswith=sku_prefix.upper(),
        ).update(subcategory=subcategory)


class Migration(migrations.Migration):
    dependencies = [
        ('shop', '0006_seed_marketplace_samples'),
    ]

    operations = [
        migrations.RunPython(create_subcategories, migrations.RunPython.noop),
    ]

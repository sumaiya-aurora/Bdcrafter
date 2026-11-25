from django.db import migrations


SAMPLE_ASSIGNMENTS = {
    'BDC-KUS-001': 'textiles',
    'BDC-KUS-002': 'handicrafts',
    'BDC-GAD-001': 'mobile-accessories',
    'BDC-GAD-002': 'power-charging',
    'BDC-DIG-001': 'website-services',
    'BDC-DIG-002': 'design-services',
    'BDC-CLO-001': 'men',
    'BDC-CLO-002': 'women',
    'BDC-ORG-001': 'organic-food',
    'BDC-ORG-002': 'organic-oils',
}


def assign_sample_subcategories(apps, schema_editor):
    SubCategory = apps.get_model('shop', 'SubCategory')
    Product = apps.get_model('shop', 'Product')
    database = schema_editor.connection.alias

    for sku, subcategory_slug in SAMPLE_ASSIGNMENTS.items():
        subcategory = SubCategory.objects.using(database).filter(
            slug=subcategory_slug,
        ).select_related('category').first()
        if subcategory:
            Product.objects.using(database).filter(sku=sku).update(
                subcategory=subcategory
            )


class Migration(migrations.Migration):
    dependencies = [
        ('shop', '0007_category_subcategories'),
    ]

    operations = [
        migrations.RunPython(assign_sample_subcategories, migrations.RunPython.noop),
    ]

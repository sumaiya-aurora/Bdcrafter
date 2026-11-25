from django.db import migrations


def update_portfolio_image_alt(apps, schema_editor):
    ProductImage = apps.get_model('shop', 'ProductImage')
    ProductImage.objects.filter(
        product__sku='BDC-DIG-001',
        alt_text='Basic Business Website Setup',
    ).update(alt_text='Portfolio Website')


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0014_seed_digital_service_packages'),
    ]

    operations = [
        migrations.RunPython(update_portfolio_image_alt, migrations.RunPython.noop),
    ]

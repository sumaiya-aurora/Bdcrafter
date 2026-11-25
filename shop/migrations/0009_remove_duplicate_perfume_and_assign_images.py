from django.db import migrations


SAMPLE_IMAGES = {
    'BDC-KUS-001': ('products/category-samples/cushion.jpg', 'Nakshi Kantha Cushion Cover'),
    'BDC-KUS-002': ('products/category-samples/cushion.jpg', 'Handwoven Jute Storage Basket'),
    'BDC-GAD-001': ('products/category-samples/earbuds.jpg', 'Wireless Bluetooth Earbuds'),
    'BDC-GAD-002': ('products/category-samples/charger.jpg', '20W USB-C Fast Charger'),
    'BDC-DIG-001': ('products/category-samples/website.jpg', 'Basic Business Website Setup'),
    'BDC-DIG-002': ('products/category-samples/design.jpg', 'Social Media Design Starter Pack'),
    'BDC-CLO-001': ('products/unsplash_5.jpg', 'Classic Cotton Panjabi'),
    'BDC-CLO-002': ('products/category-samples/kurti.jpg', 'Everyday Cotton Kurti'),
    'BDC-ORG-001': ('products/category-samples/honey.jpg', 'Raw Forest Honey 500g'),
    'BDC-ORG-002': ('products/category-samples/oil.jpg', 'Cold-Pressed Mustard Oil 1L'),
}


def clean_perfume_duplicates_and_images(apps, schema_editor):
    Product = apps.get_model('shop', 'Product')
    ProductImage = apps.get_model('shop', 'ProductImage')
    database = schema_editor.connection.alias

    for duplicate in Product.objects.using(database).filter(
        name='Hypnotic Poison',
        subcategory__slug='high-end',
    ):
        duplicate.delete()

    for product in Product.objects.using(database).filter(category__slug='perfume'):
        seen_images = set()
        for image in product.images.using(database).order_by('id'):
            image_name = str(image.image)
            if image_name in seen_images:
                image.delete()
            else:
                seen_images.add(image_name)

    for sku, (image_name, alt_text) in SAMPLE_IMAGES.items():
        product = Product.objects.using(database).filter(sku=sku).first()
        if not product:
            continue
        product.images.using(database).all().delete()
        ProductImage.objects.using(database).create(
            product=product,
            image=image_name,
            alt_text=alt_text,
            is_primary=True,
            is_featured=True,
        )


class Migration(migrations.Migration):
    dependencies = [
        ('shop', '0008_refine_sample_subcategory_assignments'),
    ]

    operations = [
        migrations.RunPython(
            clean_perfume_duplicates_and_images,
            migrations.RunPython.noop,
        ),
    ]

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from shop.models import Category, Product, ProductImage, ProductVariant, SubCategory


CATALOG = {
    'Casual Scents': [
        'Dunhil Desire', 'Eternal Love', 'Hugo Boss', 'Escape', 'Cool Water',
        'Polo Sports', 'Barbariez', 'Sporty', 'Silver Stone', 'Al Fares',
        'CK One', 'Lemon', 'Joopi', 'Axe', 'Poison', 'Lord', 'Black Open',
        'Pure Soft', 'Mixed Berry', 'Dalal', 'Red Rose', 'White Rose',
        'Fresh Beli', 'Rajanigandha', 'Hasnahena', 'Choco Musk',
        'One Man Show', 'Brut Musk',
    ],
    'Elite Section': [
        'Dunhil Icon', 'Aqua Di Gio', 'Hypnotic Poison', 'Rush', 'Gucci Flora',
        'Midnight Flora', 'Pink Lotus', 'Sensual', 'Imagination', 'Siger',
        'Stronger W.U', 'Chocolate', 'Vanilla', 'Durk Coffee', 'Dior Sauvage',
        'Blue de Channel', 'One Million', 'Black Opium', 'Mashmoom',
        'Havoc Gold', 'Joven Musk',
    ],
    'High-End': [
        'YSL My Self', 'Hypnotic Poison', 'Bulgarian Rose', 'Creed Aventus',
        'Nishane Hacivat', 'Paris Hilton', 'Escada Moon', 'Vampire Blood',
        'Baccarat Rouge', 'Arabian Bakhur', 'Irani Bakhur', 'White Oud',
        'Fantasy Purple', 'Lavender Musk', 'Egyptian Musk', 'Blue Berry Musk',
    ],
    'Elegant Collection': [
        'Musk Shapphire', 'Egyptian Bakhur', 'Zafran Musk', 'Mazmua',
        "Musk Al ka'ba",
    ],
}

SIZES = (
    ('3ml', Decimal('150.00')),
    ('6ml', Decimal('250.00')),
    ('15ml', Decimal('500.00')),
)


class Command(BaseCommand):
    help = 'Load the fragrance catalog with 3ml, 6ml, and 15ml variants'

    def handle(self, *args, **options):
        category = Category.objects.get(slug='perfume')
        created_count = 0
        variant_count = 0

        for category_name, product_names in CATALOG.items():
            subcategory, _ = SubCategory.objects.get_or_create(
                category=category,
                slug=slugify(category_name),
                defaults={'name': category_name},
            )
            for product_name in product_names:
                if Product.objects.filter(category=category, name=product_name).exists():
                    continue
                slug = slugify(f'{category_name}-{product_name}')
                is_featured = product_name in [
                    'Dior Sauvage', 'Blue de Channel', 'Creed Aventus', 'Baccarat Rouge',
                    'Aqua Di Gio', 'Eternal Love', 'One Million', 'Black Opium',
                    'Dunhil Icon', 'White Oud', 'Durk Coffee', "Musk Al ka'ba"
                ]
                product, created = Product.objects.get_or_create(
                    slug=slug,
                    defaults={
                        'name': product_name,
                        'sku': f'FRG-{slug.upper()[:70]}',
                        'category': category,
                        'subcategory': subcategory,
                        'price': SIZES[0][1],
                        'stock': 50,
                        'description': f'{product_name} fragrance from the {category_name} collection.',
                        'short_description': product_name,
                        'published': True,
                        'featured': is_featured,
                        'draft': False,
                    },
                )
                if not created:
                    continue

                created_count += 1
                from .update_product_images import IMAGE_MAP
                img_name = IMAGE_MAP.get(product_name, 'aurum_luxury_gold.webp')
                ProductImage.objects.create(
                    product=product,
                    image=f'products/{img_name}',
                    alt_text=f'{product_name} - Premium Fragrance & Attar',
                    is_primary=True,
                    is_featured=True,
                )
                ProductVariant.objects.bulk_create([
                    ProductVariant(product=product, name=size, price=price, stock=50)
                    for size, price in SIZES
                ])
                variant_count += len(SIZES)

        self.stdout.write(self.style.SUCCESS(
            f'Perfume catalog ready: {created_count} new products and {variant_count} variants created.'
        ))
        self.stdout.write('Existing products and other category data were left unchanged.')

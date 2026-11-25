from django.core.management.base import BaseCommand
from shop.models import Product, ProductImage

IMAGE_MAP = {
    # Rouge / Crimson luxury
    'Baccarat Rouge': 'rouge_eclat_red.webp',
    'Dunhil Desire': 'rouge_eclat_red.webp',
    'Hypnotic Poison': 'rouge_eclat_red.webp',
    'Rush': 'rouge_eclat_red.webp',
    'Poison': 'rouge_eclat_red.webp',
    'Vampire Blood': 'rouge_eclat_red.webp',
    
    # Noir / Dark luxury
    'Dior Sauvage': 'noir_sauvage_dark.webp',
    'Black Open': 'noir_sauvage_dark.webp',
    'Siger': 'noir_sauvage_dark.webp',
    'Axe': 'noir_sauvage_dark.webp',
    'YSL My Self': 'noir_sauvage_dark.webp',
    
    # Bleu / Aquatic / Fresh
    'Blue de Channel': 'bleu_de_chanel.webp',
    'Aqua Di Gio': 'acqua_di_gio_men.webp',
    'Cool Water': 'oceanic_fresh_aquatic.webp',
    'Escape': 'oceanic_fresh_aquatic.webp',
    'Silver Stone': 'oceanic_fresh_aquatic.webp',
    'Polo Sports': 'versace_eros_blue.webp',
    'Sporty': 'versace_eros_blue.webp',
    'Musk Shapphire': 'versace_eros_blue.webp',
    'Blue Berry Musk': 'versace_eros_blue.webp',
    'Fantasy Purple': 'versace_eros_blue.webp',
    'Escada Moon': 'versace_eros_blue.webp',
    
    # Men classics
    'Hugo Boss': 'boss_bottled_men.webp',
    'One Man Show': 'boss_bottled_men.webp',
    'Brut Musk': 'boss_bottled_men.webp',
    'Barbariez': 'dolce_gabbana_the_one.webp',
    'Stronger W.U': 'dolce_gabbana_the_one.webp',
    'Joven Musk': 'dolce_gabbana_the_one.webp',
    
    # Gourmand / Coffee / Vanilla
    'Durk Coffee': 'noir_absolu_espresso.webp',
    'Vanilla': 'noir_absolu_espresso.webp',
    'Chocolate': 'noir_absolu_espresso.webp',
    'Choco Musk': 'noir_absolu_espresso.webp',
    'Dalal': 'noir_absolu_espresso.webp',
    
    # Royal Attar / Oud
    'White Oud': 'royal_crown_attar_oud.webp',
    'Arabian Bakhur': 'royal_crown_attar_oud.webp',
    'Irani Bakhur': 'royal_crown_attar_oud.webp',
    'Zafran Musk': 'royal_crown_attar_oud.webp',
    'Mazmua': 'royal_crown_attar_oud.webp',
    "Musk Al ka'ba": 'royal_crown_attar_oud.webp',
    'Egyptian Bakhur': 'royal_crown_attar_oud.webp',
    'Al Fares': 'royal_crown_attar_oud.webp',
    'Mashmoom': 'royal_crown_attar_oud.webp',
    
    # Luxury Gold / Amber
    'Creed Aventus': 'aurum_luxury_gold.webp',
    'One Million': 'aurum_luxury_gold.webp',
    'Dunhil Icon': 'aurum_luxury_gold.webp',
    'Havoc Gold': 'aurum_luxury_gold.webp',
    'Sensual': 'aurum_luxury_gold.webp',
    'Imagination': 'aurum_luxury_gold.webp',
    
    # Clean Glass / Fresh
    'Nishane Hacivat': 'chopin_classic.webp',
    'CK One': 'chopin_classic.webp',
    'Lemon': 'chopin_classic.webp',
    
    # Rose and Floral
    'Eternal Love': 'eternal_love_luxury.webp',
    'Bulgarian Rose': 'eternal_love_luxury.webp',
    'Red Rose': 'coco_pink_roses.webp',
    'Gucci Flora': 'coco_pink_roses.webp',
    'Pink Lotus': 'coco_pink_roses.webp',
    'Mixed Berry': 'coco_pink_roses.webp',
    'White Rose': 'coco_cream_roses.webp',
    'Pure Soft': 'coco_cream_roses.webp',
    
    # Jasmine / Exotic Floral
    'Fresh Beli': 'armani_sun_di_gioia.webp',
    'Rajanigandha': 'armani_sun_di_gioia.webp',
    'Hasnahena': 'armani_sun_di_gioia.webp',
    
    # Dark Silk / Glamour
    'Black Opium': 'coco_black_silk.webp',
    'Midnight Flora': 'coco_black_silk.webp',
    'Lavender Musk': 'coco_black_silk.webp',
    
    # Vintage Warm Musk
    'Lord': 'golden_square_luxury.webp',
    'Egyptian Musk': 'golden_square_luxury.webp',
    
    # Chic Feminine
    'Paris Hilton': 'miss_dior_cherie.webp',
}

FEATURED_PRODUCTS = [
    'Dior Sauvage',
    'Blue de Channel',
    'Creed Aventus',
    'Baccarat Rouge',
    'Aqua Di Gio',
    'Eternal Love',
    'One Million',
    'Black Opium',
    'Dunhil Icon',
    'White Oud',
    'Durk Coffee',
    "Musk Al ka'ba"
]

SECONDARY_IMAGES = {
    'Dior Sauvage': 'bleu_de_chanel.webp',
    'Blue de Channel': 'noir_sauvage_dark.webp',
    'Creed Aventus': 'chopin_classic.webp',
    'Baccarat Rouge': 'aurum_luxury_gold.webp',
    'Aqua Di Gio': 'oceanic_fresh_aquatic.webp',
    'Eternal Love': 'coco_pink_roses.webp',
    'One Million': 'golden_square_luxury.webp',
    'Black Opium': 'noir_sauvage_dark.webp',
    'Dunhil Icon': 'noir_sauvage_dark.webp',
    'White Oud': 'golden_square_luxury.webp',
    'Durk Coffee': 'aurum_luxury_gold.webp',
    "Musk Al ka'ba": 'golden_square_luxury.webp'
}


class Command(BaseCommand):
    help = 'Assign real, non-dummy product images and configure featured images'

    def handle(self, *args, **options):
        # Remove test artifact product
        deleted, _ = Product.objects.filter(id=297).delete()
        if deleted:
            self.stdout.write(self.style.WARNING('Deleted test product ID 297.'))

        updated_count = 0
        for p in Product.objects.all():
            img_name = IMAGE_MAP.get(p.name, 'aurum_luxury_gold.webp')

            # Update featured flag
            p.featured = (p.name in FEATURED_PRODUCTS)
            p.published = True
            p.save(update_fields=['featured', 'published'])

            # Delete old images (including placeholders)
            p.images.all().delete()

            # Create primary featured image
            ProductImage.objects.create(
                product=p,
                image=f'products/{img_name}',
                alt_text=f'{p.name} - Premium Fragrance & Attar',
                is_primary=True,
                is_featured=True
            )

            # If it has a secondary image, add it
            if p.name in SECONDARY_IMAGES:
                ProductImage.objects.create(
                    product=p,
                    image=f'products/{SECONDARY_IMAGES[p.name]}',
                    alt_text=f'{p.name} - Alternate view',
                    is_primary=False,
                    is_featured=False
                )

            updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Successfully updated {updated_count} products with real images!'
        ))
        featured_count = Product.objects.filter(featured=True).count()
        self.stdout.write(self.style.SUCCESS(
            f'{featured_count} products are now marked as featured.'
        ))

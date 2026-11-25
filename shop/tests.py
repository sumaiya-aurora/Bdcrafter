from decimal import Decimal
from io import StringIO
import json
import re
import xml.etree.ElementTree as ET
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    Brand, CartItem, Category, Order, OrderItem, Product, ProductImage,
    ProductVariant, StorefrontContent, SubCategory,
)


class ShoppingFlowTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Fragrance', slug='fragrance')
        self.product = Product.objects.create(
            name='Amber Perfume', slug='amber-perfume', sku='AMBER-01',
            category=self.category, description='Warm amber scent',
            price=Decimal('800.00'), stock=5, published=True,
        )
        self.brand = Brand.objects.create(name='Bdcrafter Originals', slug='bdcrafter-originals')
        self.product.brand = self.brand
        self.product.save(update_fields=['brand'])
        self.variant = ProductVariant.objects.create(
            product=self.product, name='50 ml', price=Decimal('900.00'), stock=4,
        )

    def test_home_and_shop_navigation_show_all_store_categories(self):
        response = self.client.get(reverse('shop:home'))
        expected_categories = [
            'Kushikata',
            'Gadgets',
            'Digital Services',
            'Clothes',
            'Perfume',
            'Organic Store',
        ]
        self.assertEqual(
            [category.name for category in response.context['categories']],
            expected_categories,
        )
        for category in expected_categories:
            self.assertContains(response, category)

    def test_category_filter_only_shows_products_from_selected_category(self):
        perfume = Category.objects.get(slug='perfume')
        gadgets = Category.objects.get(slug='gadgets')
        self.product.category = perfume
        self.product.save(update_fields=['category'])
        gadget = Product.objects.create(
            name='Wireless Headphones', slug='wireless-headphones', sku='GADGET-01',
            category=gadgets, price=Decimal('2500.00'), stock=3, published=True,
        )

        response = self.client.get(
            reverse('shop:product_list'),
            {'category': 'gadgets'},
        )

        self.assertEqual(response.context['product_count'], 3)
        filtered_products = list(response.context['products'].object_list)
        self.assertIn(gadget, filtered_products)
        self.assertTrue(all(product.category == gadgets for product in filtered_products))
        self.assertContains(response, 'Gadgets')
        self.assertNotContains(response, self.product.name)

    def test_published_sample_products_exist_in_each_new_category(self):
        expected_counts = {
            'kushikata': 2,
            'gadgets': 2,
            'digital-services': 5,
            'clothes': 2,
            'organic-store': 2,
        }
        for slug, expected_count in expected_counts.items():
            with self.subTest(category=slug):
                self.assertEqual(
                    Product.objects.filter(category__slug=slug, published=True).count(),
                    expected_count,
                )

    def test_category_subcategory_filters_exist(self):
        for slug in ('kushikata', 'gadgets', 'digital-services', 'clothes', 'perfume', 'organic-store'):
            with self.subTest(category=slug):
                self.assertTrue(SubCategory.objects.filter(category__slug=slug).exists())

        kushikata = self.client.get(
            reverse('shop:product_list'),
            {'category': 'kushikata'},
        )
        collection_names = ['Traditional', 'Handicrafts', 'Textiles']
        for name in collection_names:
            self.assertContains(kushikata, name)

        perfume = Category.objects.get(slug='perfume')
        response = self.client.get(
            reverse('shop:product_list'),
            {'category': 'perfume', 'subcategory': 'casual-scents'},
        )
        self.assertContains(response, 'Casual Scents')
        self.assertTrue(
            all(product.category == perfume for product in response.context['products'].object_list)
        )

    def test_added_category_products_have_primary_images(self):
        for slug in ('kushikata', 'gadgets', 'digital-services', 'clothes', 'organic-store'):
            with self.subTest(category=slug):
                products = Product.objects.filter(category__slug=slug)
                self.assertTrue(products.exists())
                self.assertTrue(
                    all(product.primary_image is not None for product in products)
                )

    def test_public_order_tracking_shows_status_without_customer_details(self):
        order = Order.objects.create(
            order_number='RF-20261124-AB12',
            first_name='Customer',
            last_name='Name',
            email='customer@example.com',
            phone='01700000000',
            shipping_address='Private address',
            shipping_city='Dhaka',
            total=Decimal('1200.00'),
            status='shipped',
        )

        response = self.client.post(
            reverse('shop:order_tracking'),
            {'order_id': order.order_number.lower()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Shipped')
        self.assertContains(response, order.order_number)
        self.assertNotContains(response, order.email)
        self.assertNotContains(response, order.shipping_address)
        self.assertEqual(response['Cache-Control'], 'no-store')

        response_by_id = self.client.post(
            reverse('shop:order_tracking'),
            {'order_id': str(order.pk)},
        )
        self.assertContains(response_by_id, 'Shipped')

    def test_public_order_tracking_handles_unknown_order_number(self):
        response = self.client.post(
            reverse('shop:order_tracking'),
            {'order_id': 'RF-UNKNOWN'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'couldn’t find an order')

    def test_fragrance_catalog_loader_preserves_existing_products(self):
        call_command('load_fragrance_catalog', stdout=StringIO())

        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.category, self.category)
        self.assertEqual(Product.objects.filter(category__slug='perfume').count(), 69)

    def test_guest_can_add_selected_variant_and_quantity(self):
        response = self.client.post(reverse('shop:cart_add', args=[self.product.id]), {
            'variant': self.variant.id, 'quantity': 2,
        })

        self.assertEqual(response.status_code, 302)
        item = CartItem.objects.get(session_id=self.client.session.session_key)
        self.assertEqual(item.product, self.product)
        self.assertEqual(item.variant, self.variant)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.total_price(), Decimal('1800.00'))

    def test_variant_is_required_when_product_has_variants(self):
        self.client.post(reverse('shop:cart_add', args=[self.product.id]), {'quantity': 1})
        self.assertFalse(CartItem.objects.exists())

    def test_product_detail_selects_first_variant_and_uses_its_image(self):
        self.variant.image = 'products/variants/amber-50ml.webp'
        self.variant.save(update_fields=['image'])

        response = self.client.get(reverse('shop:product_detail', args=[self.product.slug]))
        html = response.content.decode()
        select_html = html.split('<select id="variant"', 1)[1].split('</select>', 1)[0]
        first_option = re.search(r'<option(?=[^>]*value="%s")(?=[^>]*selected)[^>]*>' % self.variant.id, select_html)

        self.assertIsNotNone(first_option)
        self.assertIn(f'data-price="{self.variant.price_display}"', first_option.group(0))
        self.assertIn('data-image="/media/products/variants/amber-50ml.webp"', first_option.group(0))
        self.assertNotIn('Choose an option', select_html)

    def test_featured_image_falls_back_to_primary_then_can_be_distinct(self):
        primary = ProductImage.objects.create(
            product=self.product, image='products/amber-primary.webp', is_primary=True,
        )
        self.assertEqual(self.product.featured_image, primary)

        featured = ProductImage.objects.create(
            product=self.product, image='products/amber-featured.webp', is_featured=True,
        )
        self.assertEqual(self.product.featured_image, featured)

    def test_simple_product_adds_requested_quantity_and_can_be_removed(self):
        product = Product.objects.create(
            name='Citrus Oil', slug='citrus-oil', sku='CITRUS-01',
            category=self.category, price=Decimal('300.00'), stock=6,
        )
        self.client.post(reverse('shop:cart_add', args=[product.id]), {'quantity': 3})
        item = CartItem.objects.get()
        self.assertEqual(item.quantity, 3)
        self.assertEqual(item.total_price(), Decimal('900.00'))

        self.client.post(reverse('shop:cart_remove', args=[item.id]))
        self.assertFalse(CartItem.objects.exists())

    def test_cart_add_and_update_reject_quantity_over_stock(self):
        self.client.post(reverse('shop:cart_add', args=[self.product.id]), {
            'variant': self.variant.id, 'quantity': 5,
        })
        self.assertFalse(CartItem.objects.exists())

        self.client.post(reverse('shop:cart_add', args=[self.product.id]), {
            'variant': self.variant.id, 'quantity': 2,
        })
        item = CartItem.objects.get()
        self.client.post(reverse('shop:cart_update', args=[item.id]), {'quantity': 5})
        item.refresh_from_db()
        self.assertEqual(item.quantity, 2)

    @patch('shop.views.notify_admin_new_order')
    def test_guest_cod_checkout_persists_order_and_deducts_variant_stock(self, notify_admin):
        self.client.post(reverse('shop:cart_add', args=[self.product.id]), {
            'variant': self.variant.id, 'quantity': 2,
        })
        response = self.client.post(reverse('shop:checkout'), {
            'first_name': 'Samira', 'last_name': 'Rahman',
            'email': 'samira@example.com', 'phone': '+8801712345678',
            'shipping_address': '12 Lake Road', 'shipping_city': 'Dhaka',
            'shipping_state': 'Dhaka', 'shipping_postal_code': '1205',
            'shipping_country': 'Bangladesh', 'payment_method': 'cod',
            'order_notes': 'Call on arrival',
        })

        order = Order.objects.get()
        order_item = OrderItem.objects.get(order=order)
        self.assertRedirects(response, reverse('shop:order_success', args=[order.order_number]))
        self.assertEqual(order.first_name, 'Samira')
        self.assertEqual(order.email, 'samira@example.com')
        self.assertEqual(order.status, 'pending')
        self.assertEqual(order.payment_method, 'Cash on Delivery')
        self.assertEqual(order.get_subtotal(), Decimal('1800.00'))
        self.assertEqual(order.total, Decimal('1800.00'))
        self.assertEqual(order_item.product, self.product)
        self.assertEqual(order_item.variant, self.variant)
        self.assertEqual(order_item.quantity, 2)
        self.assertEqual(order_item.unit_price, Decimal('900.00'))
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 2)
        self.assertFalse(CartItem.objects.exists())
        notify_admin.assert_called_once_with(order)

    @patch('shop.views.notify_admin_new_order')
    def test_usd_service_order_uses_usd_checkout_and_post_order_payment(self, notify_admin):
        service = Product.objects.get(name='Portfolio Website')
        self.assertEqual(service.currency, 'USD')
        self.client.post(reverse('shop:cart_add', args=[service.id]), {'quantity': 1})

        checkout = self.client.get(reverse('shop:checkout'))
        self.assertContains(checkout, 'Payment details will be shared after your service order is received.')
        self.assertContains(checkout, 'USD')

        response = self.client.post(reverse('shop:checkout'), {
            'first_name': 'Samira', 'last_name': 'Rahman',
            'email': 'samira@example.com', 'phone': '+8801712345678',
            'shipping_address': '12 Lake Road', 'shipping_city': 'Dhaka',
            'shipping_state': 'Dhaka', 'shipping_postal_code': '1205',
            'shipping_country': 'Bangladesh', 'payment_method': 'post_order',
            'order_notes': '',
        })

        order = Order.objects.get()
        self.assertRedirects(response, reverse('shop:order_success', args=[order.order_number]))
        self.assertEqual(order.currency, 'USD')
        self.assertEqual(order.payment_method, 'Payment details after order')
        self.assertEqual(order.total, Decimal('100.00'))
        self.assertFalse(order.requires_quote)
        notify_admin.assert_called_once_with(order)

    def test_admin_product_form_exposes_currency_and_quote_controls(self):
        service = Product.objects.get(name='Portfolio Website')
        staff = User.objects.create_user(username='service-editor', is_staff=True)
        self.client.force_login(staff)

        response = self.client.get(reverse('admin_panel:product_edit', args=[service.id]))

        self.assertContains(response, 'Currency')
        self.assertContains(response, 'US Dollar')
        self.assertContains(response, 'Price on request')

    @patch('shop.views.notify_admin_new_order')
    def test_custom_service_is_a_quote_order_not_a_zero_price_sale(self, notify_admin):
        service = Product.objects.get(name='Custom Digital Service')
        self.assertTrue(service.price_on_request)
        self.client.post(reverse('shop:cart_add', args=[service.id]), {'quantity': 1})

        response = self.client.post(reverse('shop:checkout'), {
            'first_name': 'Samira', 'last_name': 'Rahman',
            'email': 'samira@example.com', 'phone': '+8801712345678',
            'shipping_address': '12 Lake Road', 'shipping_city': 'Dhaka',
            'shipping_state': 'Dhaka', 'shipping_postal_code': '1205',
            'shipping_country': 'Bangladesh', 'payment_method': 'post_order',
            'order_notes': '',
        })

        order = Order.objects.get()
        self.assertRedirects(response, reverse('shop:order_success', args=[order.order_number]))
        self.assertEqual(order.currency, 'USD')
        self.assertEqual(order.total, Decimal('0.00'))
        self.assertTrue(order.requires_quote)
        self.assertContains(self.client.get(response.url), 'Quote pending')
        notify_admin.assert_called_once_with(order)

    @patch('shop.views.notify_admin_new_order')
    def test_digital_service_booking_does_not_require_or_consume_stock(self, notify_admin):
        service = Product.objects.get(name='Landing Page')
        service.stock = 0
        service.save(update_fields=['stock'])
        self.client.post(reverse('shop:cart_add', args=[service.id]), {'quantity': 1})
        self.assertEqual(CartItem.objects.get().product, service)

        response = self.client.post(reverse('shop:checkout'), {
            'first_name': 'Samira', 'last_name': 'Rahman',
            'email': 'samira@example.com', 'phone': '+8801712345678',
            'shipping_address': '12 Lake Road', 'shipping_city': 'Dhaka',
            'shipping_state': 'Dhaka', 'shipping_postal_code': '1205',
            'shipping_country': 'Bangladesh', 'payment_method': 'post_order',
            'order_notes': '',
        })

        order = Order.objects.get()
        self.assertRedirects(response, reverse('shop:order_success', args=[order.order_number]))
        service.refresh_from_db()
        self.assertEqual(service.stock, 0)
        notify_admin.assert_called_once_with(order)

    def test_cart_rejects_mixing_bdt_products_with_usd_services(self):
        self.client.post(reverse('shop:cart_add', args=[self.product.id]), {
            'variant': self.variant.id,
            'quantity': 1,
        })
        service = Product.objects.get(name='Portfolio Website')
        response = self.client.post(
            reverse('shop:cart_add', args=[service.id]),
            {'quantity': 1},
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse('shop:cart_detail'),
            status_code=302,
            target_status_code=200,
        )
        self.assertEqual(CartItem.objects.count(), 1)
        self.assertEqual(CartItem.objects.get().product, self.product)
        self.assertContains(response, 'different currency')

    def test_homepage_highlights_portfolio_and_ecommerce_between_product_sections(self):
        response = self.client.get(reverse('shop:home'))
        page = response.content.decode()

        self.assertContains(response, 'Portfolio Website')
        self.assertContains(response, 'Ecommerce Site')
        self.assertContains(response, 'Book Now')
        self.assertLess(page.index('Featured Products'), page.index('Portfolio Website'))
        self.assertLess(page.index('Ecommerce Site'), page.index('New Arrivals'))

    def test_homepage_shows_at_most_four_featured_products(self):
        for index in range(5):
            Product.objects.create(
                name=f'Featured item {index}',
                slug=f'featured-item-{index}',
                sku=f'FEATURED-{index}',
                category=self.category,
                price=Decimal('100.00'),
                stock=1,
                featured=True,
                published=True,
            )

        response = self.client.get(reverse('shop:home'))

        self.assertEqual(len(response.context['featured_products']), 4)

    def test_portfolio_service_image_alt_matches_updated_product_name(self):
        portfolio = Product.objects.get(name='Portfolio Website')
        self.assertEqual(portfolio.primary_image.alt_text, 'Portfolio Website')

    def test_checkout_searches_product_fields(self):
        response = self.client.get(reverse('shop:search'), {'q': 'fragrance', 'format': 'json'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'][0]['name'], self.product.name)

        response = self.client.get(reverse('shop:search'), {'q': 'bdcrafter originals', 'format': 'json'})
        self.assertEqual(response.json()['results'][0]['name'], self.product.name)
        response = self.client.get(reverse('shop:search'), {'q': 'AMBER-01', 'format': 'json'})
        self.assertEqual(response.json()['results'][0]['name'], self.product.name)

    def test_checkout_rejects_invalid_phone_without_creating_order(self):
        self.client.post(reverse('shop:cart_add', args=[self.product.id]), {
            'variant': self.variant.id, 'quantity': 1,
        })

        response = self.client.post(reverse('shop:checkout'), {
            'first_name': 'Samira', 'last_name': 'Rahman',
            'email': 'samira@example.com', 'phone': 'not-a-phone',
            'shipping_address': '12 Lake Road', 'shipping_city': 'Dhaka',
            'shipping_country': 'Bangladesh', 'payment_method': 'cod',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())
        self.assertTrue(CartItem.objects.exists())

    def test_checkout_rejects_inventory_that_changed_after_add(self):
        self.client.post(reverse('shop:cart_add', args=[self.product.id]), {
            'variant': self.variant.id, 'quantity': 2,
        })
        self.variant.stock = 1
        self.variant.save(update_fields=['stock'])

        self.client.post(reverse('shop:checkout'), {
            'first_name': 'Samira', 'last_name': 'Rahman',
            'email': 'samira@example.com', 'phone': '+8801712345678',
            'shipping_address': '12 Lake Road', 'shipping_city': 'Dhaka',
            'shipping_country': 'Bangladesh', 'payment_method': 'cod',
        })

        self.assertFalse(Order.objects.exists())
        self.assertTrue(CartItem.objects.exists())
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 1)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        ADMIN_EMAIL='owner@example.com',
    )
    def test_customer_invoice_is_sent_only_after_admin_confirms_order(self):
        self.client.post(reverse('shop:cart_add', args=[self.product.id]), {
            'variant': self.variant.id, 'quantity': 1,
        })
        self.client.post(reverse('shop:checkout'), {
            'first_name': 'Samira', 'last_name': 'Rahman',
            'email': 'samira@example.com', 'phone': '+8801712345678',
            'shipping_address': '12 Lake Road', 'shipping_city': 'Dhaka',
            'shipping_country': 'Bangladesh', 'payment_method': 'cod',
        })

        order = Order.objects.get()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['owner@example.com'])
        self.assertIn('Bdcrafter.com', mail.outbox[0].subject)
        self.assertNotIn('samira@example.com', [recipient for message in mail.outbox for recipient in message.to])

        staff = User.objects.create_user(username='mail-admin', is_staff=True)
        self.client.force_login(staff)
        self.client.post(
            reverse('admin_panel:order_detail', args=[order.id]),
            {'status': 'confirmed'},
        )

        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[1].to, ['samira@example.com'])
        self.assertIn('Bdcrafter.com', mail.outbox[1].subject)
        self.assertTrue(mail.outbox[1].alternatives)
        self.assertIn('Bdcrafter.com', mail.outbox[1].alternatives[0][0])
        invoice_text = mail.outbox[1].body
        self.assertIn(f'Order Number: {order.order_number}\n\n', invoice_text)
        self.assertIn('Date: November', invoice_text)
        self.assertIn('Payment Method: Cash on Delivery\n\n', invoice_text)
        self.assertIn('Status: Confirmed', invoice_text)
        self.assertIn('Order Number:</td><td>', mail.outbox[1].alternatives[0][0])
        self.assertIn('Subtotal:</td>', mail.outbox[1].alternatives[0][0])
        pdf_attachment = next(
            attachment for attachment in mail.outbox[1].attachments
            if attachment[2] == 'application/pdf'
        )
        self.assertEqual(pdf_attachment[0], f'Bdcrafter-Invoice-{order.order_number}.pdf')
        self.assertTrue(pdf_attachment[1].startswith(b'%PDF-'))

    @patch('shop.admin_views.send_customer_invoice')
    @patch('shop.views.notify_admin_new_order')
    def test_admin_can_find_order_and_update_status(self, notify_admin, send_invoice):
        self.client.post(reverse('shop:cart_add', args=[self.product.id]), {
            'variant': self.variant.id, 'quantity': 1,
        })
        self.client.post(reverse('shop:checkout'), {
            'first_name': 'Samira', 'last_name': 'Rahman',
            'email': 'samira@example.com', 'phone': '+8801712345678',
            'shipping_address': '12 Lake Road', 'shipping_city': 'Dhaka',
            'shipping_country': 'Bangladesh', 'payment_method': 'cod',
        })
        order = Order.objects.get()
        staff = User.objects.create_user(
            username='store-admin', password='development-only', is_staff=True,
        )
        self.client.force_login(staff)

        listing = self.client.get(reverse('admin_panel:orders'))
        self.assertContains(listing, order.order_number)
        self.client.post(reverse('admin_panel:order_detail', args=[order.id]), {'status': 'confirmed'})
        order.refresh_from_db()
        self.assertEqual(order.status, 'confirmed')
        send_invoice.assert_called_once_with(order)

        self.client.post(reverse('admin_panel:order_detail', args=[order.id]), {'status': 'confirmed'})
        send_invoice.assert_called_once_with(order)

    @patch('shop.views.notify_admin_new_order')
    def test_admin_orders_keeps_new_badge_until_order_is_handled(self, notify_admin):
        self.client.post(reverse('shop:cart_add', args=[self.product.id]), {
            'variant': self.variant.id, 'quantity': 1,
        })
        self.client.post(reverse('shop:checkout'), {
            'first_name': 'Samira', 'last_name': 'Rahman',
            'email': 'samira@example.com', 'phone': '+8801712345678',
            'shipping_address': '12 Lake Road', 'shipping_city': 'Dhaka',
            'shipping_country': 'Bangladesh', 'payment_method': 'cod',
        })
        order = Order.objects.get()
        staff = User.objects.create_user(username='order-admin', is_staff=True)
        self.client.force_login(staff)

        listing = self.client.get(reverse('admin_panel:orders'))
        self.assertContains(listing, 'NEW')
        order.refresh_from_db()
        self.assertTrue(order.is_new)

    def test_product_listing_has_query_preserving_pagination(self):
        for index in range(24):
            Product.objects.create(
                name=f'Fragrance {index}', slug=f'fragrance-{index}', sku=f'FRAG-{index}',
                category=self.category, price=Decimal('400.00'), stock=2,
            )

        response = self.client.get(reverse('shop:product_list'), {'category': 'fragrance'})

        self.assertEqual(response.context['product_count'], 25)
        self.assertContains(response, 'Page 1 of 2')
        self.assertContains(response, 'category=fragrance&amp;page=2')

    def test_admin_orders_requires_staff_access(self):
        response = self.client.get(reverse('admin_panel:orders'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_homepage_does_not_render_malformed_banner_syntax(self):
        response = self.client.get(reverse('shop:home'))
        self.assertContains(response, 'home-hero')
        self.assertNotContains(response, ') center/cover no-repeat;">')


class StorefrontContentTests(TestCase):
    def test_homepage_restores_default_copy_if_storefront_content_is_missing(self):
        StorefrontContent.objects.all().delete()

        response = self.client.get(reverse('shop:home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Craft worth')
        self.assertContains(response, 'Explore Store')
        self.assertContains(response, 'Shop by Category')
        self.assertContains(response, 'Bdcrafter')
        self.assertContains(response, 'Shop All')
        self.assertContains(response, 'Free Delivery')

    def test_store_staff_can_edit_homepage_content_from_store_admin(self):
        staff_user = User.objects.create_user(username='store-editor', is_staff=True)
        self.client.force_login(staff_user)

        response = self.client.get(reverse('admin_panel:storefront_content'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Homepage &amp; Footer')
        self.assertContains(response, 'Save homepage and footer')
        self.assertNotContains(response, 'hero_stat_one_value')
        self.assertNotContains(response, 'Hero statistics')
        self.assertContains(response, 'Hero side card copy')
        self.assertContains(response, 'name="hero_card_title_lead"')

        content = StorefrontContent.objects.get(pk=1)
        from .forms import StorefrontContentForm
        form = StorefrontContentForm(instance=content)
        data = {name: form[name].value() for name in form.fields}
        data['home_cta_title'] = 'Updated store staff CTA'
        data['hero_card_title_lead'] = 'Updated side card copy'
        for prefix in ('header', 'footer', 'feature'):
            data[f'{prefix}-TOTAL_FORMS'] = '0'
            data[f'{prefix}-INITIAL_FORMS'] = '0'
            data[f'{prefix}-MIN_NUM_FORMS'] = '0'
            data[f'{prefix}-MAX_NUM_FORMS'] = '1000'

        response = self.client.post(reverse('admin_panel:storefront_content'), data)

        self.assertRedirects(response, reverse('admin_panel:storefront_content'))
        content.refresh_from_db()
        self.assertEqual(content.home_cta_title, 'Updated store staff CTA')
        self.assertEqual(content.hero_card_title_lead, 'Updated side card copy')

    def test_homepage_and_global_navigation_render_admin_managed_copy_and_urls(self):
        content = StorefrontContent.objects.get(pk=1)
        content.hero_primary_label = 'Browse handmade'
        content.hero_primary_url = '/products/?category=kushikata'
        content.home_category_heading = 'Explore collections'
        content.footer_contact_heading = 'Get in touch'
        content.footer_phone_text = '+880 1700 000000'
        content.footer_phone_url = 'tel:+8801700000000'
        content.save()

        header_link = content.header_links.get(label='Shop')
        header_link.label = 'Explore'
        header_link.url = '/products/?category=kushikata'
        header_link.save()

        footer_link = content.footer_links.get(label='Shop All')
        footer_link.label = 'Browse catalog'
        footer_link.url = '/products/?category=kushikata'
        footer_link.save()

        response = self.client.get(reverse('shop:home'))

        self.assertContains(response, 'Browse handmade')
        self.assertContains(response, 'href="/products/?category=kushikata"')
        self.assertContains(response, 'Explore collections')
        self.assertContains(response, 'Get in touch')
        self.assertContains(response, 'tel:+8801700000000')
        self.assertContains(response, 'Browse catalog')

    def test_storefront_content_is_editable_in_django_admin(self):
        admin_user = User.objects.create_superuser(
            username='content-admin',
            email='content-admin@example.com',
            password='test-password',
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse('admin:shop_storefrontcontent_change', args=(1,)))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Homepage and footer content')
        self.assertContains(response, 'Header navigation links')
        self.assertContains(response, 'Footer navigation links')
        self.assertNotContains(response, 'hero_stat_one_value')

    def test_homepage_does_not_render_hero_statistics_below_buttons(self):
        content = StorefrontContent.objects.get(pk=1)
        content.hero_card_title_lead = 'A custom right-side headline'
        content.save()

        response = self.client.get(reverse('shop:home'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'hero-stats')
        self.assertNotContains(response, 'hero_stat_one_value')
        self.assertContains(response, 'hero-feature-card')
        self.assertContains(response, 'A custom right-side headline')

    def test_storefront_urls_reject_script_schemes(self):
        content = StorefrontContent.objects.get(pk=1)
        content.brand_url = 'javascript:alert(1)'

        with self.assertRaises(ValidationError):
            content.full_clean()


class SeoTests(TestCase):
    def test_homepage_has_canonical_social_metadata_and_website_schema(self):
        response = self.client.get(reverse('shop:home'))
        content = response.content.decode()

        canonical_url = response.context['canonical_url']
        self.assertEqual(canonical_url, response.wsgi_request.build_absolute_uri('/'))
        self.assertContains(response, f'<link rel="canonical" href="{canonical_url}" />')
        self.assertContains(response, 'property="og:site_name"')
        self.assertContains(response, 'name="twitter:card"')
        self.assertContains(response, '"@type": "WebSite"')
        self.assertIn('Shop Kushikata, Gadgets & More in Bangladesh', content)

    def test_category_page_has_unique_copy_and_filtered_urls_are_noindex(self):
        category_url = reverse('shop:product_list')
        response = self.client.get(category_url, {'category': 'gadgets'})

        self.assertContains(response, 'Shop everyday gadgets and accessories')
        self.assertEqual(
            response.context['canonical_url'],
            'http://testserver/products/?category=gadgets',
        )
        self.assertEqual(response.context['seo_robots'], 'index,follow')

        filtered_response = self.client.get(
            category_url,
            {'category': 'gadgets', 'sort': 'price_asc'},
        )
        self.assertEqual(filtered_response.context['seo_robots'], 'noindex,follow')
        self.assertEqual(
            filtered_response.context['canonical_url'],
            'http://testserver/products/?category=gadgets',
        )

        invalid_subcategory_response = self.client.get(
            category_url,
            {'category': 'gadgets', 'subcategory': 'unknown'},
        )
        self.assertEqual(
            invalid_subcategory_response.context['seo_robots'],
            'noindex,follow',
        )
        self.assertEqual(
            invalid_subcategory_response.context['canonical_url'],
            'http://testserver/products/?category=gadgets',
        )

    def test_sitemap_uses_request_host_and_includes_public_catalog_urls(self):
        response = self.client.get(reverse('sitemap'))
        sitemap_root = ET.fromstring(response.content)
        locations = [
            node.text
            for node in sitemap_root.findall(
                './/{http://www.sitemaps.org/schemas/sitemap/0.9}loc'
            )
        ]

        self.assertEqual(response.status_code, 200)
        self.assertIn('http://testserver/', locations)
        self.assertIn('http://testserver/about/', locations)
        self.assertTrue(any('/product/' in location for location in locations))
        self.assertFalse(any('localhost' in location for location in locations))

    def test_robots_lists_absolute_sitemap_url(self):
        response = self.client.get('/robots.txt')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sitemap: http://testserver/sitemap.xml')
        self.assertContains(response, 'Disallow: /store-admin/')

    def test_published_draft_products_are_not_public_or_listed_in_sitemap(self):
        draft = Product.objects.create(
            name='Unreleased Gadget',
            slug='unreleased-gadget',
            sku='UNRELEASED-01',
            category=Category.objects.get(slug='gadgets'),
            description='Internal draft product.',
            price=Decimal('100.00'),
            published=True,
            draft=True,
        )

        listing_response = self.client.get(reverse('shop:product_list'))
        detail_response = self.client.get(draft.get_absolute_url())
        sitemap_response = self.client.get(reverse('sitemap'))

        self.assertNotContains(listing_response, 'Unreleased Gadget')
        self.assertEqual(detail_response.status_code, 404)
        self.assertNotContains(sitemap_response, '/product/unreleased-gadget/')

    def test_search_pages_are_noindex(self):
        response = self.client.get(reverse('shop:search'), {'q': 'earbuds'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['seo_robots'], 'noindex,follow')

    def test_product_page_has_valid_product_json_ld_and_no_placeholder_copy(self):
        product = Product.objects.get(slug='bdc-gad-001')
        response = self.client.get(product.get_absolute_url())
        scripts = re.findall(
            r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
            response.content.decode(),
            re.DOTALL,
        )
        product_schema = next(
            json.loads(script)
            for script in scripts
            if '"@type": "Product"' in script
        )

        self.assertEqual(product_schema['name'], product.name)
        self.assertEqual(product_schema['offers'][0]['priceCurrency'], 'BDT')
        self.assertNotContains(response, 'Sample catalog listing')

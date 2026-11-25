from django.urls import path
from shop import admin_views

app_name = 'admin_panel'

urlpatterns = [
    path('', admin_views.admin_dashboard, name='dashboard'),
    path('storefront/', admin_views.admin_storefront_content, name='storefront_content'),
    path('orders/', admin_views.admin_orders, name='orders'),
    path('orders/<int:order_id>/', admin_views.admin_order_detail, name='order_detail'),
    path('orders/<int:order_id>/invoice/', admin_views.admin_order_invoice, name='order_invoice'),
    path('products/', admin_views.admin_products, name='products'),
    path('products/add/', admin_views.admin_product_add, name='product_add'),
    path('products/<int:product_id>/edit/', admin_views.admin_product_edit, name='product_edit'),
    path('products/<int:product_id>/delete/', admin_views.admin_product_delete, name='product_delete'),
]


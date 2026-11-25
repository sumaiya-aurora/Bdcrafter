from django.urls import path
from . import views

app_name = 'shop'

urlpatterns = [
    # Home
    path('', views.home, name='home'),

    # Products
    path('products/', views.product_list, name='product_list'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('search/', views.search, name='search'),

    # Cart (guest + logged-in)
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:item_id>/', views.cart_remove, name='cart_remove'),
    path('cart/update/<int:item_id>/', views.cart_update, name='cart_update'),

    # Wishlist (login required)
    path('wishlist/', views.wishlist_detail, name='wishlist_detail'),
    path('wishlist/add/<int:product_id>/', views.wishlist_add, name='wishlist_add'),
    path('wishlist/remove/<int:item_id>/', views.wishlist_remove, name='wishlist_remove'),
    path('wishlist/move-to-cart/<int:item_id>/', views.wishlist_move_to_cart, name='wishlist_move_to_cart'),

    # Checkout & Orders (guest checkout supported)
    path('checkout/', views.checkout, name='checkout'),
    path('order/success/<str:order_number>/', views.order_success, name='order_success'),
    path('order-tracking/', views.order_tracking, name='order_tracking'),
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('orders/', views.order_history, name='order_history'),
    path('order/<int:order_id>/cancel/', views.order_cancel, name='order_cancel'),

    # Account
    path('account/dashboard/', views.dashboard, name='dashboard'),
    path('account/profile/', views.profile, name='profile'),
    path('account/addresses/', views.address_list, name='address_list'),
    path('account/address/add/', views.address_add, name='address_add'),
    path('account/address/<int:address_id>/edit/', views.address_edit, name='address_edit'),
    path('account/address/<int:address_id>/delete/', views.address_delete, name='address_delete'),

    # Reviews & Q&A
    path('review/<int:product_id>/', views.submit_review, name='submit_review'),
    path('question/<int:product_id>/', views.submit_question, name='submit_question'),
    path('coupon/apply/', views.apply_coupon, name='apply_coupon'),

    # Auth
    path('register/', views.register, name='register'),
    path('activate/sent/', views.activation_sent, name='activation_sent'),
    path('activate/<uidb64>/<token>/', views.activate, name='activate'),

    # Static pages
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('faq/', views.faq, name='faq'),
    path('policies/privacy/', views.privacy, name='privacy'),
    path('policies/terms/', views.terms, name='terms'),
    path('policies/shipping/', views.shipping_policy, name='shipping_policy'),
    path('policies/returns/', views.returns_policy, name='returns_policy'),
]

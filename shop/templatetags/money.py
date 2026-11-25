from django import template

register = template.Library()


@register.filter
def currency_symbol(currency):
    return '$' if currency == 'USD' else '৳'

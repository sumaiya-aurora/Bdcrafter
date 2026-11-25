"""
Email utility functions for order notifications.
Admin email and customer invoice email are sent here.
If email fails, the error is logged but does NOT break checkout.
"""
import logging
from email.utils import formataddr
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)
BRAND_NAME = 'Bdcrafter.com'


def _branded_from_email(email_address):
    return formataddr((BRAND_NAME, email_address))


def _find_pdf_browser():
    configured_browser = getattr(settings, 'PDF_BROWSER_PATH', '')
    if configured_browser and Path(configured_browser).is_file():
        return configured_browser

    for browser_name in ('msedge', 'chrome', 'chromium', 'chromium-browser', 'google-chrome'):
        browser_path = shutil.which(browser_name)
        if browser_path:
            return browser_path

    if os.name == 'nt':
        for browser_path in (
            Path(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)')) /
            'Microsoft/Edge/Application/msedge.exe',
            Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')) /
            'Microsoft/Edge/Application/msedge.exe',
            Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')) /
            'Google/Chrome/Application/chrome.exe',
        ):
            if browser_path.is_file():
                return str(browser_path)
    raise RuntimeError(
        'A Chromium-based browser is required to generate the printable invoice PDF. '
        'Configure PDF_BROWSER_PATH or install Chrome/Edge.'
    )


def _create_customer_invoice_pdf(order):
    browser = _find_pdf_browser()
    html_content = render_to_string('admin_panel/order_invoice.html', {
        'order': order,
        'store_name': BRAND_NAME,
        'store_phone': getattr(settings, 'STORE_PHONE', '+880 1234 567890'),
        'store_address': getattr(settings, 'STORE_ADDRESS', 'Dhaka, Bangladesh'),
        'admin_email': getattr(settings, 'ADMIN_EMAIL', ''),
    })

    with tempfile.TemporaryDirectory(prefix='bdcrafter-invoice-') as temp_directory:
        temp_path = Path(temp_directory)
        html_path = temp_path / 'invoice.html'
        pdf_path = temp_path / 'invoice.pdf'
        profile_path = temp_path / 'browser-profile'
        html_path.write_text(html_content, encoding='utf-8')
        subprocess.run(
            [
                browser,
                '--headless',
                '--disable-gpu',
                '--no-pdf-header-footer',
                f'--user-data-dir={profile_path}',
                f'--print-to-pdf={pdf_path}',
                html_path.resolve().as_uri(),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        pdf_content = pdf_path.read_bytes()

    if not pdf_content.startswith(b'%PDF-'):
        raise RuntimeError('Browser did not generate a valid invoice PDF.')
    return pdf_content


def notify_admin_new_order(order):
    """Notify the store admin when a new order is placed."""
    try:
        _send_admin_notification(order)
    except Exception as e:
        logger.error(f'[ORDER EMAIL] Admin notification failed for order {order.order_number}: {e}')


def send_customer_invoice(order):
    """Send the customer invoice after the admin confirms the order."""
    try:
        _send_customer_invoice(order)
    except Exception as e:
        logger.error(f'[ORDER EMAIL] Customer invoice failed for order {order.order_number}: {e}')


def _send_admin_notification(order):
    """Send new order notification to store admin."""
    admin_email = getattr(settings, 'ADMIN_EMAIL', None)
    if not admin_email:
        logger.warning('[ORDER EMAIL] ADMIN_EMAIL not configured — skipping admin notification.')
        return

    store_name = BRAND_NAME
    subject = f'[{store_name}] New Order #{order.order_number}'

    html_content = render_to_string('shop/emails/admin_order_notification.html', {
        'order': order,
        'store_name': store_name,
    })
    text_content = render_to_string('shop/emails/admin_order_notification.txt', {
        'order': order,
        'store_name': store_name,
    })

    from_email = _branded_from_email(
        getattr(settings, 'FROM_EMAIL', settings.DEFAULT_FROM_EMAIL)
    )
    msg = EmailMultiAlternatives(subject, text_content, from_email, [admin_email])
    msg.attach_alternative(html_content, 'text/html')
    msg.send()
    logger.info(f'[ORDER EMAIL] Admin notification sent for order {order.order_number}')


def _send_customer_invoice(order):
    """Send professional invoice email to the customer."""
    if not order.email:
        logger.warning(f'[ORDER EMAIL] No customer email for order {order.order_number} — skipping.')
        return

    store_name = BRAND_NAME
    subject = f'Your {store_name} Order Confirmation — #{order.order_number}'

    html_content = render_to_string('shop/emails/customer_invoice.html', {
        'order': order,
        'store_name': store_name,
        'store_phone': getattr(settings, 'STORE_PHONE', ''),
        'store_address': getattr(settings, 'STORE_ADDRESS', ''),
    })
    text_content = render_to_string('shop/emails/customer_invoice.txt', {
        'order': order,
        'store_name': store_name,
        'store_phone': getattr(settings, 'STORE_PHONE', ''),
        'store_address': getattr(settings, 'STORE_ADDRESS', ''),
    })

    from_email = _branded_from_email(
        getattr(settings, 'FROM_EMAIL', settings.DEFAULT_FROM_EMAIL)
    )
    msg = EmailMultiAlternatives(subject, text_content, from_email, [order.email])
    msg.attach_alternative(html_content, 'text/html')
    invoice_pdf = _create_customer_invoice_pdf(order)
    msg.attach(
        f'Bdcrafter-Invoice-{order.order_number}.pdf',
        invoice_pdf,
        'application/pdf',
    )
    msg.send()
    logger.info(f'[ORDER EMAIL] Customer invoice sent to {order.email} for order {order.order_number}')

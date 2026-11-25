import re
from django import forms
from .context_processors import STORE_CATEGORY_SLUGS
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    Address,
    Brand,
    Category,
    Coupon,
    FooterNavigationLink,
    HeaderNavigationLink,
    HomepageTrustFeature,
    Product,
    ProductImage,
    Question,
    Review,
    StorefrontContent,
)
from django.utils.text import slugify


class FormFieldMixin:
    """Adds consistent styling to form fields."""
    field_css = (
        'w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 '
        'focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 focus:outline-none '
        'transition placeholder-slate-400 text-sm'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            existing = widget.attrs.get('class', '')
            widget.attrs['class'] = (existing + ' ' + self.field_css).strip()


# Keep TailwindFormMixin as an alias for backward compatibility
TailwindFormMixin = FormFieldMixin


class UserRegistrationForm(FormFieldMixin, UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with that email already exists.')
        return email


class ProfileForm(FormFieldMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']


class AddressForm(FormFieldMixin, forms.ModelForm):
    class Meta:
        model = Address
        fields = [
            'label', 'address_line1', 'address_line2',
            'city', 'state', 'postal_code', 'country',
            'phone', 'address_type', 'default',
        ]


class CouponApplyForm(FormFieldMixin, forms.Form):
    code = forms.CharField(max_length=60, label='Coupon code')


class ReviewForm(FormFieldMixin, forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'title', 'comment']
        widgets = {
            'rating': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'comment': forms.Textarea(attrs={'rows': 4}),
        }


class QuestionForm(FormFieldMixin, forms.ModelForm):
    class Meta:
        model = Question
        fields = ['question']
        widgets = {
            'question': forms.Textarea(attrs={'rows': 3}),
        }


class GuestCheckoutForm(FormFieldMixin, forms.Form):
    """
    Checkout form that works for BOTH guests and logged-in users.
    No login required. All validation is done here.
    """
    first_name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={'placeholder': 'First name', 'id': 'id_first_name'}),
    )
    last_name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={'placeholder': 'Last name', 'id': 'id_last_name'}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'Email address', 'id': 'id_email'}),
    )
    phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'placeholder': 'Phone number (e.g. 01712345678)', 'id': 'id_phone'}),
    )
    shipping_address = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'placeholder': 'Street / area / road', 'id': 'id_shipping_address'}),
    )
    shipping_city = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'City (e.g. Dhaka)', 'id': 'id_shipping_city'}),
    )
    shipping_state = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Division / state (optional)', 'id': 'id_shipping_state'}),
    )
    shipping_postal_code = forms.CharField(
        max_length=40,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Postal code (optional)', 'id': 'id_shipping_postal_code'}),
    )
    shipping_country = forms.CharField(
        max_length=100,
        initial='Bangladesh',
        widget=forms.TextInput(attrs={'placeholder': 'Country', 'id': 'id_shipping_country'}),
    )
    order_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Any special instructions? (optional)', 'id': 'id_order_notes'}),
    )
    payment_method = forms.ChoiceField(
        choices=[('cod', 'Cash on Delivery')],
        widget=forms.RadioSelect,
        initial='cod',
    )
    coupon_code = forms.CharField(max_length=60, required=False)

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        digits = re.sub(r'\D', '', phone)
        if not 8 <= len(digits) <= 15:
            raise ValidationError('Enter a valid phone number with 8 to 15 digits.')
        return phone

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        return email

    def clean_first_name(self):
        val = self.cleaned_data.get('first_name', '').strip()
        if not val:
            raise ValidationError('First name is required.')
        return val

    def clean_shipping_address(self):
        val = self.cleaned_data.get('shipping_address', '').strip()
        if not val:
            raise ValidationError('Shipping address is required.')
        return val

    def clean_shipping_city(self):
        val = self.cleaned_data.get('shipping_city', '').strip()
        if not val:
            raise ValidationError('City is required.')
        return val


# Keep old CheckoutForm for backward compat
CheckoutForm = GuestCheckoutForm


class ContactForm(FormFieldMixin, forms.Form):
    name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'placeholder': 'Your name'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Your email'}))
    subject = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'placeholder': 'Subject'}))
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 5, 'placeholder': 'Your message...'}))


class AdminProductForm(forms.ModelForm):
    image = forms.ImageField(required=False, label='Product Image')
    featured_image = forms.ImageField(required=False, label='Featured Image')

    class Meta:
        model = Product
        fields = [
            'name', 'category', 'brand', 'sku', 'price', 'currency',
            'price_on_request', 'sale_price', 'stock', 'short_description',
            'description', 'published', 'featured'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Amber Oud Luxury EDP'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'brand': forms.Select(attrs={'class': 'form-control'}),
            'sku': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank to auto-generate (e.g. RF-AOD-100)'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'sale_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Optional discount price'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'short_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Brief 1-2 sentence overview'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Full product or service description, features, details, etc.'}),
            'published': forms.CheckboxInput(attrs={'style': 'width: 1.15rem; height: 1.15rem; accent-color: var(--primary);'}),
            'featured': forms.CheckboxInput(attrs={'style': 'width: 1.15rem; height: 1.15rem; accent-color: var(--primary);'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(
            slug__in=STORE_CATEGORY_SLUGS,
        )
        self.fields['sku'].required = False
        self.fields['category'].required = False
        self.fields['brand'].required = False
        self.fields['short_description'].required = False
        self.fields['description'].required = False
        self.fields['sale_price'].required = False

    def save(self, commit=True):
        import uuid, random, string
        instance = super().save(commit=False)
        if not instance.slug:
            base_slug = slugify(instance.name) or f"product-{uuid.uuid4().hex[:6]}"
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=instance.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            instance.slug = slug

        if not instance.sku:
            suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
            instance.sku = f"RF-{suffix}"

        if commit:
            instance.save()
            image = self.cleaned_data.get('image')
            if image:
                primary = instance.images.filter(is_primary=True).first()
                if primary:
                    primary.image = image
                    primary.save()
                else:
                    ProductImage.objects.create(product=instance, image=image, is_primary=True)
            featured_image = self.cleaned_data.get('featured_image')
            if featured_image:
                featured = instance.images.filter(is_featured=True).first()
                if featured:
                    featured.image = featured_image
                    featured.save()
                else:
                    ProductImage.objects.create(
                        product=instance,
                        image=featured_image,
                        alt_text=f'Featured image for {instance.name}',
                        is_featured=True,
                    )
        return instance


class StorefrontAdminFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['style'] = (
                    'width:1.15rem;height:1.15rem;accent-color:var(--primary);'
                )
            else:
                field.widget.attrs['class'] = 'form-control'


class StorefrontContentForm(StorefrontAdminFormMixin, forms.ModelForm):
    class Meta:
        model = StorefrontContent
        fields = [
            'brand_name', 'brand_suffix', 'brand_url',
            'hero_eyebrow', 'hero_background_url', 'hero_title_lead',
            'hero_title_emphasis', 'hero_description_prefix', 'hero_brand_text',
            'hero_description_suffix', 'hero_primary_label', 'hero_primary_url',
            'hero_secondary_label', 'hero_secondary_url',
            'hero_card_eyebrow', 'hero_card_title_lead', 'hero_card_title_emphasis',
            'hero_card_tag_one', 'hero_card_tag_two', 'hero_card_tag_three',
            'hero_card_footer',
            'home_category_heading', 'home_category_link_label', 'home_category_link_url',
            'home_featured_heading', 'home_featured_link_label', 'home_featured_link_url',
            'home_arrivals_heading', 'home_arrivals_link_label', 'home_arrivals_link_url',
            'home_product_view_label', 'home_product_new_badge', 'home_product_sale_badge',
            'home_cta_eyebrow', 'home_cta_title', 'home_cta_description',
            'home_cta_button_label', 'home_cta_button_url', 'home_cta_background_url',
            'footer_brand_description', 'footer_quick_links_heading',
            'footer_policies_heading', 'footer_contact_heading', 'footer_address_text',
            'footer_address_url', 'footer_phone_text', 'footer_phone_url',
            'footer_email_text', 'footer_email_url', 'footer_whatsapp_text',
            'footer_whatsapp_url', 'footer_facebook_label', 'footer_facebook_url',
            'footer_instagram_label', 'footer_instagram_url', 'footer_country_text',
            'footer_copyright_text',
        ]
        widgets = {
            'hero_description_prefix': forms.Textarea(attrs={'rows': 3}),
            'home_cta_description': forms.Textarea(attrs={'rows': 3}),
            'footer_brand_description': forms.Textarea(attrs={'rows': 3}),
        }


class HeaderNavigationLinkForm(StorefrontAdminFormMixin, forms.ModelForm):
    class Meta:
        model = HeaderNavigationLink
        fields = ['label', 'url', 'placement', 'sort_order', 'is_active']


class FooterNavigationLinkForm(StorefrontAdminFormMixin, forms.ModelForm):
    class Meta:
        model = FooterNavigationLink
        fields = ['section', 'label', 'url', 'sort_order', 'is_active']


class HomepageTrustFeatureForm(StorefrontAdminFormMixin, forms.ModelForm):
    class Meta:
        model = HomepageTrustFeature
        fields = ['icon', 'title', 'description', 'sort_order', 'is_active']


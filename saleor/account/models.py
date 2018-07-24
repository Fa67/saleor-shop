import uuid

from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser, BaseUserManager, PermissionsMixin)
from django.db import models
from django.db.models import Q
from django.forms.models import model_to_dict
from django.utils import timezone
from django.utils.translation import pgettext_lazy
from django_countries.fields import Country, CountryField
from phonenumber_field.modelfields import PhoneNumberField

from ..core.models import BaseNote
from .validators import validate_possible_number


class PossiblePhoneNumberField(PhoneNumberField):
    """Less strict field for phone numbers written to database."""

    default_validators = [validate_possible_number]


class Address(models.Model):
    first_name = models.CharField(max_length=256, default = "")
    last_name = models.CharField(max_length=256, default = "")
    company_name = models.CharField(max_length=256, default = "")
    street_address_1 = models.CharField(max_length=256, default = "")
    street_address_2 = models.CharField(max_length=256, default = "")
    city = models.CharField(max_length=256,default = "")
    city_area = models.CharField(max_length=128, default = "")
    postal_code = models.CharField(max_length=20, default = "")
    country = CountryField(default = "Russian Federation")
    country_area = models.CharField(max_length=128, default = "")
    phone = PossiblePhoneNumberField(blank=True, default='')

    @property
    def full_name(self):
        return '%s %s' % (self.first_name, self.last_name)

    def __str__(self):
        if self.company_name:
            return '%s - %s' % (self.company_name, self.full_name)
        return self.full_name

    def __repr__(self):
        return (
            'Address(first_name=%r, last_name=%r, country=%r, country_area=%r, phone=%r)' % (
                self.first_name, self.last_name, self.country, self.country_area,
                self.phone))

    def __eq__(self, other):
        return self.as_data() == other.as_data()

    def as_data(self):
        """Return the address as a dict suitable for passing as kwargs.

        Result does not contain the primary key or an associated user.
        """
        data = model_to_dict(self, exclude=['id', 'user'])
        if isinstance(data['country'], Country):
            data['country'] = data['country'].code
        return data

    def get_copy(self):
        """Return a new instance of the same address."""
        return Address.objects.create(**self.as_data())


class UserManager(BaseUserManager):

    def create_user(
            self, email, password=None, is_staff=False, is_active=True,
            **extra_fields):
        """Create a user instance with the given email and password."""
        email = UserManager.normalize_email(email)
        # Google OAuth2 backend send unnecessary username field
        extra_fields.pop('username', None)

        user = self.model(
            email=email, is_active=is_active, is_staff=is_staff,
            **extra_fields)
        if password:
            user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        return self.create_user(
            email, password, is_staff=True, is_superuser=True, **extra_fields)

    def customers(self):
        return self.get_queryset().filter(
            Q(is_staff=False) | (Q(is_staff=True) & Q(orders__isnull=False)))

    def staff(self):
        return self.get_queryset().filter(is_staff=True)


def get_token():
    return str(uuid.uuid4())


class User(PermissionsMixin, AbstractBaseUser):
    first_name = models.CharField(max_length=256, default = "")
    last_name = models.CharField(max_length=256, default = "")

    phone = PossiblePhoneNumberField(blank=True, default='')

    email = models.EmailField(unique=True)
    addresses = models.ManyToManyField(
        Address, blank=True, related_name='user_addresses')
    is_staff = models.BooleanField(default=False)
    token = models.UUIDField(default=get_token, editable=False, unique=True)
    is_active = models.BooleanField(default=True)
    note = models.TextField(null=True, blank=True)
    date_joined = models.DateTimeField(default=timezone.now, editable=False)
    default_shipping_address = models.ForeignKey(
        Address, related_name='+', null=True, blank=True,
        on_delete=models.SET_NULL)
    default_billing_address = models.ForeignKey(
        Address, related_name='+', null=True, blank=True,
        on_delete=models.SET_NULL)

    USERNAME_FIELD = 'email'

    objects = UserManager()

    class Meta:
        permissions = (
            ('view_user',
             pgettext_lazy('Permission description', 'Может просматривать пользователей')),
            ('edit_user',
             pgettext_lazy('Permission description', 'Может редактировать пользователей')),
            ('view_staff',
             pgettext_lazy('Permission description', 'Может смотреть админов')),
            ('edit_staff',
             pgettext_lazy('Permission description', 'Может изменять админов')),
            ('impersonate_user',
             pgettext_lazy('Permission description', 'Может заходить от лица других пользователей')))

    def get_full_name(self):
        return self.email

    def get_short_name(self):
        return self.email

    def get_ajax_label(self):
        if self.first_name:
            return '%s %s (%s)' % (
                self.first_name, self.last_name, self.email)
        return self.email


class CustomerNote(BaseNote):
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='notes',
        on_delete=models.CASCADE)

    class Meta:
        ordering = ('date', )

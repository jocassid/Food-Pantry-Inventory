

from django.contrib.auth.models import User
from django.test import Client


default_password = 'abc123'


def create_user(first_name, last_name):
    first_name = first_name.lower()
    last_name = last_name.lower()

    return User.objects.create_user(
        first_name[0] + last_name,
        f"{first_name}.{last_name}",
        default_password,
    )


def logged_in_user(first_name, last_name):
    user = create_user(first_name, last_name)
    client = Client()
    client.force_login(user)
    return client
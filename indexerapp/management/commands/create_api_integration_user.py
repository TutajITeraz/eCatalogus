"""Grant an account the right to write through the public API.

Two uses:

    # give an existing person API import rights — nothing else about them changes
    python manage.py create_api_integration_user akowalska

    # create a dedicated unattended account
    python manage.py create_api_integration_user ritus-bot --password '...'

    # revoke
    python manage.py create_api_integration_user akowalska --remove

Membership of the ``api_importers`` group is what grants the access. Running this
also creates that group, so it becomes selectable in the Django admin without
having to run a migration.

An account created here is deliberately not staff and not a superuser: it can
import through the API and nothing else.
"""

import secrets

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from indexerapp.api_access import API_IMPORTER_GROUP


class Command(BaseCommand):
    help = 'Create or update an API integration account in the api_importers group.'

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('--password', help='Generated and printed if omitted.')
        parser.add_argument('--email', default='')
        parser.add_argument(
            '--remove',
            action='store_true',
            help='Revoke API write access by removing the account from the group.',
        )

    def handle(self, *args, **options):
        username = options['username']
        user_model = get_user_model()
        group, _ = Group.objects.get_or_create(name=API_IMPORTER_GROUP)

        if options['remove']:
            user = user_model.objects.filter(username=username).first()
            if user is None:
                self.stdout.write(self.style.WARNING(f'No user named "{username}".'))
                return
            user.groups.remove(group)
            self.stdout.write(self.style.SUCCESS(
                f'Removed "{username}" from {API_IMPORTER_GROUP}; API write access revoked.'
            ))
            return

        user = user_model.objects.filter(username=username).first()
        created = user is None

        if created:
            # A brand new account exists only to import; it gets no admin rights.
            password = options['password'] or secrets.token_urlsafe(24)
            user = user_model.objects.create_user(
                username=username,
                email=options['email'],
                password=password,
            )
            user.is_staff = False
            user.is_superuser = False
            user.save()
        else:
            # Never silently reset a real person's password or strip their admin
            # rights just because someone granted them API access.
            password = options['password']
            if password:
                user.set_password(password)
                user.save()

        user.groups.add(group)

        if created:
            self.stdout.write(self.style.SUCCESS(f'Created API integration account "{username}".'))
            if not options['password']:
                self.stdout.write(f'Generated password: {password}')
                self.stdout.write(self.style.WARNING('Store it now — it is not recoverable.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Granted API import access to the existing account "{username}".'
            ))
            if password:
                self.stdout.write(self.style.WARNING('Its password was reset as requested.'))
            else:
                self.stdout.write('Its password and admin rights were left untouched.')

        self.stdout.write(
            'Authentication is HTTP Basic with this username and password over HTTPS.'
        )

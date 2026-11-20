from django.core.management.base import BaseCommand

from app.models import Enrollment
from app.views import create_installment_subscription


class Command(BaseCommand):
    help = (
        "Create the missing Stripe auto-pay subscription for paid instalment enrolments "
        "that do not have one yet (use --dry-run to only list them)."
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        missing = Enrollment.objects.filter(
            payment_plan='installment', status='paid', payment_provider='stripe',
            stripe_subscription_id__isnull=True,
        ) | Enrollment.objects.filter(
            payment_plan='installment', status='paid', payment_provider='stripe',
            stripe_subscription_id='',
        )

        for enrollment in missing.distinct():
            label = f'#{enrollment.id} {enrollment.student.email} ({enrollment.course.slug})'
            if options['dry_run']:
                self.stdout.write(f'Missing subscription: {label}')
                continue
            sub_id = create_installment_subscription(enrollment, enrollment.payment_id)
            if sub_id:
                self.stdout.write(self.style.SUCCESS(f'Created {sub_id} for {label}'))
            else:
                self.stdout.write(self.style.ERROR(f'FAILED for {label} - check: journalctl -u sysfotech_gunicorn'))

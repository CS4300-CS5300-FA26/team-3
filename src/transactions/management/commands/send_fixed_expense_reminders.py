"""Email due fixed expense notices without resending the same occurrence."""

from datetime import date, timedelta
from smtplib import SMTPException

from django.conf import settings
from django.core.mail import BadHeaderError, send_mail
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from transactions.models import Transaction


class Command(BaseCommand):
    help = "Email fixed expenses inside each student's saved reminder window."

    def add_arguments(self, parser):
        parser.add_argument("--date", help="Check date in YYYY-MM-DD format.")

    def handle(self, *args, **options):
        try:
            today = date.fromisoformat(options["date"]) if options["date"] else timezone.localdate()
        except ValueError as error:
            raise CommandError("Date must use YYYY-MM-DD format.") from error

        schedules = Transaction.objects.filter(
            kind=Transaction.Kind.EXPENSE,
            is_fixed=True,
            is_demo=False,
            recurrence__in=[
                Transaction.Recurrence.DAILY,
                Transaction.Recurrence.WEEKLY,
                Transaction.Recurrence.MONTHLY,
            ],
            next_due_date__range=(today, today + timedelta(days=30)),
            owner__is_active=True,
        ).select_related("owner").order_by("pk")

        sent = 0
        failed = 0
        for schedule in schedules:
            if (schedule.next_due_date - today).days > schedule.reminder_days:
                continue
            try:
                with transaction.atomic():
                    current = (
                        Transaction.objects.select_for_update(of=("self",))
                        .select_related("owner")
                        .get(pk=schedule.pk)
                    )
                    due = current.next_due_date
                    # A payment or edit could have changed the schedule since
                    # the initial query; check it again while holding its lock.
                    if not (
                        current.kind == Transaction.Kind.EXPENSE
                        and current.is_fixed
                        and not current.is_demo
                        and current.recurrence in {
                            Transaction.Recurrence.DAILY,
                            Transaction.Recurrence.WEEKLY,
                            Transaction.Recurrence.MONTHLY,
                        }
                        and due is not None
                        and 0 <= (due - today).days <= current.reminder_days
                        and current.owner is not None
                        and current.owner.is_active
                        and current.owner.email
                        and current.last_reminded_due_date != due
                    ):
                        continue
                    due_label = f"{due:%B} {due.day}, {due.year}"
                    delivered = send_mail(
                        f"Upcoming fixed expense: {' '.join(current.description.split())}",
                        f"{current.description} of ${current.amount:.2f} is due on {due_label}.",
                        settings.DEFAULT_FROM_EMAIL,
                        [current.owner.email],
                    )
                    if delivered != 1:
                        raise OSError("Email backend did not deliver the reminder")
                    current.last_reminded_due_date = due
                    current.save(update_fields=["last_reminded_due_date"])
                    sent += 1
            except Transaction.DoesNotExist:
                # A student may delete the schedule while this check runs.
                continue
            except (SMTPException, OSError, BadHeaderError):
                failed += 1

        self.stdout.write(f"Sent {sent} fixed expense reminder(s).")
        if failed:
            raise CommandError(f"Failed to send {failed} fixed expense reminder(s).")

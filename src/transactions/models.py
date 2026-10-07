from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Trim
from django.db.models.lookups import Exact


class Transaction(models.Model):
    """One entry in a student's budget: money received or money spent."""

    class Kind(models.TextChoices):
        INCOME = "income", "Income"
        EXPENSE = "expense", "Expense"

    kind = models.CharField(max_length=7, choices=Kind.choices)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    date = models.DateField()
    description = models.CharField(max_length=200)
    category = models.CharField(max_length=50, blank=True)
    is_fixed = models.BooleanField(default=False)
    is_demo = models.BooleanField(default=False, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        # Enforced by the database, so objects.create() and save() cannot
        # store rows that skip the form-level validation in clean().
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind__in=["income", "expense"]),
                name="transaction_kind_valid",
                violation_error_message="Kind must be income or expense.",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="transaction_amount_positive",
                violation_error_message="Amount must be greater than zero.",
            ),
            models.CheckConstraint(
                # Trim first so a category of only spaces counts as missing.
                condition=~models.Q(kind="expense")
                | ~models.Q(Exact(Trim("category"), "")),
                name="transaction_expense_has_category",
                violation_error_message="Choose a category.",
            ),
        ]

    def __str__(self):
        return f"{self.date} {self.description} ({self.get_kind_display()} ${self.amount})"

    def clean(self):
        super().clean()
        if self.kind == self.Kind.EXPENSE and not self.category.strip():
            raise ValidationError({"category": "Choose a category."})

    @property
    def signed_amount(self):
        """Amount as it affects the remaining budget: income adds, expenses subtract."""
        if self.kind == self.Kind.EXPENSE:
            return -self.amount
        return self.amount

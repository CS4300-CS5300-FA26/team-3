from django.shortcuts import render

from .models import Transaction


def transaction_list(request):
    """Render the landing page with transactions from the database."""
    transactions = Transaction.objects.all()

    return render(
        request,
        "transactions/transaction_list.html",
        {"transactions": transactions},
    )

from django.urls import path

from . import views

urlpatterns = [
    path("income/", views.record_income, name="record_income"),
    path("expense/", views.record_expense, name="record_expense"),
]

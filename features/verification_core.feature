@issue_10
Feature: Registration email verification core
  This increment covers signed-token helpers, not the full D1 UI or email delivery.

  Background:
    Given the verification core has an isolated database

  Scenario: A valid token and matching passwords create an account
    When the verification core issues a token for " Student@Example.COM "
    Then the verification core reads "student@example.com" without creating a user
    When the verification core completes registration with matching valid passwords
    Then the account foundation stores "student@example.com" as one active ordinary identity

  Scenario: An expired token cannot complete registration
    When the verification core receives a token older than 24 hours
    Then the verification core rejects registration without creating a user

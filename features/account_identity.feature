@issue_10
Feature: Account creation after mailbox verification
  Shared helpers validate email identities and create ordinary Django users.

  Background:
    Given the account foundation has an isolated database and already verified mailbox ownership

  Scenario: A non-UCCS email becomes a usable ordinary account
    When the account foundation creates "  O'Neil+Budget@Example.COM  " with a valid password
    Then the account foundation stores "o'neil+budget@example.com" as one active ordinary identity
    And Django can authenticate that account foundation identity

  Scenario: A short password does not create an account
    When the account foundation receives a seven-character password
    Then the account foundation rejects it without creating a user

  Scenario: A duplicate identity leaves the original account intact
    When the account foundation creates "student@example.com" with a valid password
    And the account foundation tries a case and whitespace variant with a different password
    Then the account foundation retains one user with the original password

  Scenario: Email uniqueness applies to users with different usernames
    When a Django user is saved with username "first-account" and email "Student@Example.COM"
    And another username tries to use "  STUDENT@example.com  "
    Then the database rejects the duplicate email and keeps the first user

  Scenario: An international domain is stored as an ASCII identity
    When the account foundation creates "Student@BÜCHER.example" with a valid password
    Then the account foundation stores "student@xn--bcher-kva.example" as one active ordinary identity
    And Django can authenticate that account foundation identity

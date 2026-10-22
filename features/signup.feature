@issue_10
Feature: Request a BudgetWise signup email
  Scenario: Start signup with any valid email domain and finish from the email
    Given the verification core has an isolated database
    When the student requests signup for "student@example.org"
    Then signup displays the generic Check your email page
    And signup emails a verification link without creating an account
    When the student opens the verification page and submits matching valid passwords
    Then the account foundation stores "student@example.org" as one active ordinary identity
    And the student sees Account created and a Sign in button without being signed in
    When the new student signs in and records income and an expense
    Then the dashboard shows only the student's saved entries
    When the student signs out of BudgetWise
    Then protected pages lead to the sign-in screen

  Scenario: Existing addresses receive an owner notice with the same public confirmation
    Given the verification core has an isolated database
    And signup already has an account for "student@example.org"
    When the student requests signup for "student@example.org"
    Then signup displays the generic Check your email page
    And signup emails the existing owner a notice without a verification link

@issue_10
Feature: Complete registration from a verification link
  Scenario: Set a password within 24 hours and sign in separately
    Given the verification core has an isolated database
    When the verification core issues a token for "student@uccs.edu"
    And the student opens the verification page and submits matching valid passwords
    Then the account foundation stores "student@uccs.edu" as one active ordinary identity
    And the student sees Account created and a Sign in button without being signed in
    And the verification link is no longer usable

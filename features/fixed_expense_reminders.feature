@issue_28
Feature: Email an upcoming fixed expense reminder
  The daily check sends email for a student's saved reminder window, without text messages.

  Background:
    Given I am signed in
    And a monthly fixed expense "Rent" of $650.00 is due on 2026-11-01

  Scenario: The daily check emails Rent without a text message
    Given today is 2026-10-29 for fixed expense reminders
    When the daily fixed expense reminder check runs
    Then I receive a Rent reminder email
    And no text message is sent

  Scenario: A custom notice emails Rent inside its window
    Given Rent's email notice is set to 14 days
    And today is 2026-10-20 for fixed expense reminders
    When the daily fixed expense reminder check runs
    Then I receive a Rent reminder email
    And no text message is sent

  Scenario: No email is sent before the notice window
    Given Rent's email notice is set to 14 days
    And today is 2026-10-17 for fixed expense reminders
    When the daily fixed expense reminder check runs
    Then no Rent reminder email is sent

@issue_74
Feature: Record and manage transactions from dashboard dialogs
  Background:
    Given I am signed in

  Scenario: Correct an invalid expense without losing the draft
    When I submit an expense dialog with an invalid amount
    Then the dialog keeps my description and shows its validation error
    When I correct the dialog amount and save
    Then the expense is saved for my account without a redirect

  Scenario: Change and delete an existing transaction through its dialog
    Given I have a transaction to manage from the dashboard
    When I change its description through the dialog
    Then the saved transaction has the new description
    When I confirm deletion through the existing delete route
    Then the transaction is deleted and confirmed without a redirect

  Scenario: New transactions use the Mountain calendar date in the evening
    When I open transaction forms after midnight UTC in winter and summer
    Then each new transaction defaults to the current Mountain date

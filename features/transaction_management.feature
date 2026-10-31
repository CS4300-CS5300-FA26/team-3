@issue_19
Feature: Edit or delete a transaction
  A signed-in student can manage their own transactions.

  Background:
    Given an isolated personal dashboard
    And I have an existing expense for transaction management

  Scenario: Edit an existing expense
    When I edit my expense amount to $75.00
    Then my expense amount is updated to $75.00
    And my remaining budget reflects the edited expense

  Scenario: Delete an existing expense
    When I open the deletion confirmation page
    Then I see the deletion confirmation
    When I confirm the transaction deletion
    Then the transaction no longer exists
    And my remaining budget reflects the deleted expense

  Scenario: Cancel transaction deletion
    When I open the deletion confirmation page
    And I cancel transaction deletion
    Then the transaction still exists

  Scenario: Prevent editing another user's transaction
    Given the expense belongs to another user
    When I attempt to edit the transaction
    Then the transaction request is rejected

  Scenario: Prevent deleting another user's transaction
    Given the expense belongs to another user
    When I attempt to delete the transaction
    Then the transaction request is rejected

  Scenario: Dashboard displays transaction actions
    When I view my transaction dashboard
    Then I see Edit and Delete links for my transaction
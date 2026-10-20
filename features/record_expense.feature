@issue_18
Feature: Record an expense
  Scenario: Expense requires a category
    Given I am signed in to record expenses
    When I add an expense of $12.50 with no category selected
    Then I see "Choose a category"
    And no entry is created

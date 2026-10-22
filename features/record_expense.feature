@issue_18
Feature: Record an expense
  Scenario: Expense requires a category
    Given I am signed in
    When I add an expense of $12.50 with no category selected
    Then I see "Choose a category"
    And no entry is created

  Scenario: Fixed expense is recorded
    Given I am signed in
    When I add an expense of $650.00 for "Rent" in category Housing marked Fixed
    Then the entry appears in my transaction list
    And my remaining budget decreases by $650.00

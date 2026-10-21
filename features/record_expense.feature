@issue_18
Feature: Record an expense
  Scenario: Expense requires a category
    Given I am signed in to record expenses
    When I add an expense of $12.50 with no category selected
    Then I see "Choose a category"
    And no entry is created

  # Pending until transactions belong to users (D2, #11): the dashboard
  # shows demo transactions only, so the list and budget steps fail today.
  @wip
  Scenario: Fixed expense is recorded
    Given I am signed in
    When I add an expense of $650.00 for "Rent" in category Housing marked Fixed
    Then the entry appears in my transaction list
    And my remaining budget decreases by $650.00

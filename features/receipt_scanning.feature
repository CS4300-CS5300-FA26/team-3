Feature: Scan a receipt to pre-fill an expense
  As a signed-in BudgetWise user
  I want to scan a receipt
  So that I can enter expenses more quickly

  Scenario: Successfully extract a receipt total
    Given I am signed in
    When I upload a receipt with a total of $64.44
    Then the scanner returns an amount of $64.44
    And no expense is created by scanning

  Scenario: Receipt total cannot be detected
    Given I am signed in
    When I upload a receipt with no readable total
    Then the scanner returns a manual-entry message
    And I can manually save an expense of $25.00

  Scenario: Unsupported receipt file
    Given I am signed in
    When I upload an unsupported receipt file
    Then the receipt upload is rejected
    And no expense is created by scanning

  Scenario: Receipt scanning requires authentication
    Given I am signed in
    When I sign out and attempt to scan a receipt
    Then the receipt upload requires authentication
    And no expense is created by scanning

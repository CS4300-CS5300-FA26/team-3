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

  Scenario: Scan a multi-picture JPEG receipt
    Given I am signed in
    When I upload a multi-picture JPEG receipt
    Then the scanner returns an amount of $64.44
    And no expense is created by scanning

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

  Scenario: Receipt uploads leave room for the Lambda request envelope
    Given I am signed in
    When I upload a receipt larger than 4 MiB
    Then the oversized receipt is rejected before scanning
    And no expense is created by scanning

  Scenario: A scan does not replace the review and save step
    Given I am signed in
    When I upload a receipt with a total of $64.44
    Then no expense is created by scanning
    When I save the reviewed receipt as a monthly expense of $65.00
    Then the reviewed amount and monthly reminder settings are saved

  Scenario: Receipt service is unavailable
    Given I am signed in
    When the receipt provider is unavailable
    Then the receipt scan offers manual entry without provider details
    And no expense is created by scanning

  Scenario: Repeated receipt scans are bounded
    Given I am signed in
    When I request six receipt scans within an hour
    Then only five scans reach the receipt provider

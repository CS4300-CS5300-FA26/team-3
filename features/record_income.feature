@issue_12
Feature: Record income
  Scenario: Non-positive amount is rejected
    Given I am signed in to record income
    When I add income of $0.00 dated 2026-10-02 with source "Part-time job"
    Then I see "Amount must be greater than zero"
    And no entry is created

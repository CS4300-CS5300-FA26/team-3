@issue_22
Feature: Warn when the remaining budget is below a safety threshold
  The signed-in student sees a warning for the selected month when needed.

  Background:
    Given an isolated personal dashboard
    And my low-balance threshold is $150.00

  Scenario: Warning shown below the threshold
    Given my remaining budget for October 2026 is $120.00
    When I view the dashboard
    Then I see "You are below your $150.00 safety threshold"

  Scenario: No warning above the threshold
    Given my remaining budget for October 2026 is $310.00
    When I view the dashboard
    Then no low-balance warning is shown

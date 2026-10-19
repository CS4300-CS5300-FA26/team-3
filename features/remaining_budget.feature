@issue_21
Feature: View remaining budget for a calendar month
  The public dashboard currently uses synthetic demo transactions only.

  Background:
    Given an isolated demo dashboard

  Scenario: Remaining budget for a month
    Given I have demo income of $1,200.00 and expenses of $830.00 dated in October 2026
    When I view the dashboard with the timeframe set to October 2026
    Then I see a remaining budget of $370.00

  Scenario: Period with no transactions
    Given I have no transactions dated in December 2026
    When I set the timeframe to December 2026
    Then I see a remaining budget of $0.00
    And I see "No transactions in this period"

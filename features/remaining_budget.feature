@issue_21
Feature: View remaining budget for a calendar month
  The signed-in student sees only their own real transactions.

  Background:
    Given an isolated personal dashboard

  Scenario: Remaining budget for a month
    Given I have income of $1,200.00 and expenses of $830.00 dated in October 2026
    When I view the dashboard with the timeframe set to October 2026
    Then I see a remaining budget of $370.00

  Scenario: Period with no transactions
    Given I have no transactions dated in December 2026
    When I set the timeframe to December 2026
    Then I see a remaining budget of $0.00
    And I see "No transactions in this period"

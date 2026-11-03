Feature: Filter transaction history by period
  Signed-in students can focus their transaction history without changing their monthly budget.

  Background:
    Given an isolated personal dashboard

  Scenario Outline: Transactions are filtered by the selected preset
    Given I am signed in and today is 2026-11-15
    When I select "<period>"
    Then only my transactions dated from <start> through 2026-11-15 inclusive are listed

    Examples:
      | period       | start      |
      | Last 3 days  | 2026-11-13 |
      | Last 7 days  | 2026-11-09 |
      | Last 14 days | 2026-11-02 |
      | This month   | 2026-11-01 |
      | This quarter | 2026-10-01 |

  Scenario: Totals reflect the selected period
    Given I have income of $200.00 and expenses of $42.50 in the selected period
    And I have other transactions outside that period
    When I filter my transaction history
    Then the income total is $200.00 and the expense total is $42.50
    And my remaining budget and low-balance warnings are unchanged

  Scenario: No transactions match the period
    Given I have no transactions in the selected period
    When I filter my transaction history
    Then I see "No transactions in this period"
    And both income and expense totals are $0.00

  Scenario: Clearing the filter restores all transactions
    Given I have a time-period filter selected
    When I select "All time"
    Then all of my transactions are listed
    And the income and expense totals reflect all of my transactions

Feature: Explain my spending
  A signed-in student can get a short explanation of spending from a selected period.

  Background:
    Given an isolated personal dashboard

  Scenario: Summary is generated from a month of activity
    Given I have at least 10 transactions in October 2026
    When I select "Explain my spending" for October 2026
    Then I see at most 3 observations
    And each observation names a category and a dollar amount from my own transactions

  Scenario: Not enough activity to summarize
    Given I have fewer than 10 transactions in the selected period
    When I select "Explain my spending" for October 2026
    Then I see "Not enough activity yet to summarize"
    And no request is sent to the AI service

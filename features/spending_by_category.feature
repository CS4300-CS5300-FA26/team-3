@issue_20
Feature: See spending by category
  Background:
    Given I am signed in

  Scenario: Categories are totaled and ranked
    Given I have October 2026 expenses of $650.00 Housing, $120.00 Food and $60.00 Books
    When I view the category breakdown for October 2026
    Then I see a horizontal bar chart with one bar per category: Housing $650.00, Food $120.00 and Books $60.00
    And the categories are ordered from highest to lowest

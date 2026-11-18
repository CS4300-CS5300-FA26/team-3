Feature: Explore monthly spending from the dashboard (#74)
  Monthly figures remain distinct from independent transaction-history periods.

  Background:
    Given I am signed in
    And my exploration records span November and October

  Scenario: Category selection replaces an independent history preset
    When I open November exploration with All time history
    And I follow the Food category bar
    Then only my November Food expenses are listed
    And the monthly figures still include every November transaction

  Scenario: Remove one criterion and clear all criteria
    When I explore Food expenses on November 3
    And I remove the category criterion
    Then all my expenses on November 3 are listed
    When I clear the exploration filters
    Then all my November transactions are listed

  Scenario: A preset clears drill-down criteria
    When I request All time with stale monthly criteria
    Then all my personal exploration records are listed
    And no exploration criteria remain

  Scenario: Requesting an explanation keeps the selected category and day
    When I explore Food expenses on November 3
    And I request an explanation of the displayed spending
    Then the explanation keeps only my Food expenses on November 3
    And the monthly figures still include every November transaction

  Scenario: The cumulative chart stops today without hiding future records
    When I view November exploration on November 16
    Then the chart includes flat zero-spend days through November 16
    And future expenses remain in the monthly total while the chart labels its end date

@issue_28
Feature: Choose when a fixed expense reminder appears
  Each monthly fixed expense starts with a three-day notice.
  A student may choose any notice from 1 to 30 days before its due date.

  Background:
    Given I am signed in
    And I have a monthly Rent schedule due on 2026-11-01 for notice settings

  Scenario: The default notice shows Rent three days before it is due
    When I view the Rent reminder on 2026-10-29
    Then I see "Rent of $650.00 is due in 3 days"

  Scenario: No reminder appears outside the default notice window
    When I view the Rent reminder on 2026-10-20
    Then no Rent reminder appears for the selected notice

  Scenario: A custom notice shows Rent earlier
    When I save a 14-day notice for Rent
    And I view the Rent reminder on 2026-10-20
    Then I see "Rent of $650.00 is due in 12 days"

  Scenario: A 30-day notice is accepted
    When I save a 30-day notice for Rent
    And I view the Rent reminder on 2026-10-02
    Then I see "Rent of $650.00 is due in 30 days"

  Scenario: More than 30 days is rejected
    When I submit a 31-day notice for Rent
    Then the reminder notice field shows a validation error

  Scenario: Recording a matching Rent payment clears its reminder
    When I save a 14-day notice for Rent
    And I view the Rent reminder on 2026-10-20
    Then I see "Rent of $650.00 is due in 12 days"
    When I record the matching Rent payment on 2026-10-20
    And I view the Rent reminder on 2026-10-20
    Then no Rent reminder appears for the selected notice

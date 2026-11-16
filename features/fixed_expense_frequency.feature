@issue_28
Feature: Daily and weekly fixed expense reminders
  A fixed expense can repeat more often than monthly without extra reminder actions.

  Scenario Outline: A recurring expense reminds and advances after payment
    Given I am signed in
    When I save a fixed expense with a <frequency> schedule due on 2026-10-29
    Then the <frequency> expense is due in 2 days on the dashboard
    When I record its matching payment on 2026-10-28
    Then its next due date is <next_due>

    Examples:
      | frequency | next_due   |
      | daily     | 2026-10-30 |
      | weekly    | 2026-11-05 |

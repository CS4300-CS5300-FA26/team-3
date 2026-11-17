@issue_25
Feature: Set a recurrence schedule for a fixed expense
  Background:
    Given I am signed in

  Scenario: A fixed expense gets a monthly recurrence schedule
    Given I am adding an expense of $650.00 for "Rent" marked as Fixed
    When I save it with a monthly recurrence and next due date of 2026-11-01
    Then "Rent" shows a next due date of 2026-11-01

  Scenario: A variable expense cannot be scheduled
    Given I am adding an expense of $4.50 for "Coffee" marked as Variable
    When I view recurrence scheduling
    Then no recurrence schedule is offered

@issue_23
Feature: Reset a forgotten password from the sign-in screen
  As a student who has forgotten my password,
  I want to reset it from the sign-in screen,
  so that I can recover my account without losing my saved budget.

  Scenario: Reset link is sent to a known email
    Given an account exists for "student@uccs.edu"
    When I select "Forgot password" and submit "student@uccs.edu"
    Then I see "If an account matches, password reset instructions will be sent"
    And a reset link is sent to that account's email address

  Scenario: An unknown email reveals nothing
    Given no account exists for "nobody@uccs.edu"
    When I select "Forgot password" and submit "nobody@uccs.edu"
    Then I see "If an account matches, password reset instructions will be sent"
    And no reset email is sent

  Scenario: The new password replaces the old one
    Given I hold a valid reset link for "student@uccs.edu"
    When I set a new password of at least 8 characters
    Then I can sign in with the new password
    And the old password is refused
    And my other signed-in sessions are signed out

  Scenario: An expired reset link is refused
    Given my reset link for "student@uccs.edu" was sent more than 30 minutes ago
    When I open the link
    Then I see "This link has expired. Request a new one."
    And my password is unchanged

  Scenario: Repeated reset requests are throttled
    Given 5 password resets were requested for "student@uccs.edu" in the last hour
    When I request another reset for "student@uccs.edu"
    Then I see "If an account matches, password reset instructions will be sent"
    And no new reset email is sent

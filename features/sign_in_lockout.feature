@issue_11
Feature: Student sign in and sign out
  As a returning student
  I want to sign in
  So that I see my own budget and nobody else's

  Scenario: Signing in shows my saved data
    Given I have an account with 3 saved transactions
    When I sign in with the correct email and password
    Then I see my dashboard
    And my 3 transactions are listed

  Scenario: Wrong password is refused
    Given I have an account with email "student@uccs.edu"
    When I sign in with "student@uccs.edu" and an incorrect password
    Then I see "Email or password is incorrect"
    And I remain on the sign-in screen

  Scenario: An unknown email gets the same message
    Given no account exists for "nobody@uccs.edu"
    When I sign in with "nobody@uccs.edu" and any password
    Then I see "Email or password is incorrect"
    And I see a "Create account" link
    And I remain on the sign-in screen

  Scenario: Signing out ends the session
    Given I am signed in
    When I select Sign out
    Then I am returned to the sign-in screen
    And my dashboard is not reachable without signing in again

  Scenario: Repeated failed sign-ins are throttled
    Given 5 failed sign-ins for "student@uccs.edu" in the last 15 minutes
    When I sign in again with any password
    Then I see "Too many attempts. Try again in 15 minutes."
    And the password is not checked


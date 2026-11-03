@issue_23
Feature: Request password reset instructions
  These service scenarios use a test-only completion route and local email.
  Public forgot-password pages and browser confirmation are the next increment.

  Background:
    Given the password reset core has an isolated database
    And the reset request service uses local email and a test completion route

  Scenario: A known address receives a usable reset link
    Given a resettable account exists for "student@uccs.edu"
    When the reset request service receives " Student@UCCS.EDU. "
    Then the reset service returns "If an account matches, password reset instructions will be sent"
    And the reset email contains a valid thirty-minute token for "student@uccs.edu"

  Scenario: An unknown address receives the same confirmation without mail
    When the reset request service receives "nobody@uccs.edu"
    Then the reset service returns "If an account matches, password reset instructions will be sent"
    And the reset service has sent 0 emails

  Scenario: Five admitted requests throttle further requests for the normalized email
    Given a resettable account exists for "student@uccs.edu"
    When 5 reset requests arrive at minute 0
    And the reset request service receives " Student@UCCS.EDU. "
    Then the reset service returns "If an account matches, password reset instructions will be sent"
    And the reset service has sent 5 emails

  Scenario: The rolling hour frees only expired admissions
    Given a resettable account exists for "student@uccs.edu"
    When 1 reset requests arrive at minute 0
    And 4 reset requests arrive at minute 59
    And 2 reset requests arrive at minute 60
    Then the reset service returns "If an account matches, password reset instructions will be sent"
    And the reset service has sent 6 emails

  Scenario: Transport failure retains the common confirmation
    Given a resettable account exists for "student@uccs.edu"
    When the reset request service receives a request while email is unavailable
    Then the reset service returns "If an account matches, password reset instructions will be sent"
    And the reset service has sent 0 emails

  Scenario: Staged delivery never emails a link to an absent completion page
    Given a resettable account exists for "student@uccs.edu"
    When the reset service is called without the test completion route
    Then the reset service returns "If an account matches, password reset instructions will be sent"
    And the reset service has sent 0 emails

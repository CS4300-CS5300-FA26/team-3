@issue_23
Feature: Forgotten password reset core
  This increment covers password replacement, expiry and recovery from lockout.
  Reset email delivery, request throttling and public pages follow separately.

  Background:
    Given the password reset core has an isolated database
    And a student has a reset token and two signed-in sessions

  Scenario: A valid reset replaces the password and signs out existing sessions
    When the password reset core accepts matching new passwords
    Then the student can sign in only with the new password
    And both previous sessions require sign-in

  Scenario: An expired reset cannot change the password
    When the password reset core receives a token older than 30 minutes
    Then the reset is refused and the old password still works

  Scenario: Successful recovery clears the student's sign-in lockout
    Given the student is locked out after five failed sign-ins
    When the password reset core accepts matching new passwords
    Then the student can sign in only with the new password

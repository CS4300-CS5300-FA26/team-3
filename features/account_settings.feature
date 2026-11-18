@issue_74 @issue_54
Feature: Shared navigation, account preferences and missing pages
  Background:
    Given I am signed in

  Scenario: Set a zero threshold in Account and return to the dashboard
    When I save an Account safety threshold of $0.00
    Then the Account threshold is $0.00
    And the dashboard keeps entry actions without a threshold editor
    And the Account amount input has no number stepper

  Scenario: Request recovery for the signed-in account
    When I request a password reset from Account
    Then Account acknowledges my password reset request

  Scenario Outline: Missing application pages have a useful recovery link
    Given I am <session> for a missing page
    When I open a missing application page
    Then I receive a generic 404 with <destination>

    Examples:
      | session    | destination       |
      | signed in  | Back to dashboard |
      | signed out | Go to sign in     |

  Scenario Outline: Dashboard navigation appears only where useful
    Given the navigation visitor is <session>
    When I visit "<path>" through the shared layout
    Then the header Dashboard link is <visibility>

    Examples:
      | session    | path                 | visibility |
      | signed in  | /account/            | visible    |
      | signed in  | /dashboard/          | hidden     |
      | signed in  | /                    | hidden     |
      | signed in  | /missing-navigation/ | visible    |
      | signed out | /sign-in/            | hidden     |
      | signed out | /missing-navigation/ | hidden     |

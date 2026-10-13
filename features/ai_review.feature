@issue_41
Feature: Automated pull request review and coverage feedback
  Scenario: Related acceptance criteria inform the review
    Given a pull request references an issue with Gherkin acceptance criteria
    When the automated review completes
    Then the model receives the scenario and proposed changes
    And feedback identifying the reviewed commit is posted

  Scenario: Review failures are visible
    Given a pull request references an issue with Gherkin acceptance criteria
    When the review API fails
    Then the review fails without posting clean feedback

  Scenario: New commits invalidate an in-progress review
    Given a pull request references an issue with Gherkin acceptance criteria
    When the pull request changes during review
    Then the review fails without posting clean feedback

  Scenario Outline: Line coverage controls the CI gate
    Given measured line coverage is <covered> out of 100 lines
    When the coverage check runs
    Then the coverage check <result>

    Examples:
      | covered | result |
      | 79      | fails  |
      | 80      | passes |

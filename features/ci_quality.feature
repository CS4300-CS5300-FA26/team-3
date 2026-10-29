@issue_41
Feature: Deterministic CI feedback
  # Sprint 1 feedback follow-up to the existing CI and coverage story.
  Scenario Outline: Python lint reports errors independently of AI review
    Given a Python sample with <condition>
    When the CI lint command checks the sample
    Then the lint check <result>

    Examples:
      | condition                    | result |
      | valid code                   | passes |
      | an undefined name            | fails  |
      | multiple statements per line | fails  |

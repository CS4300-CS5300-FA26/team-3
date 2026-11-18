Feature: Monthly spending details (#74, #9)
  Scenario: Income counts toward activity and history does not change monthly explanations
    Given I am signed in for monthly spending details
    And I have nine incomes and one expense in November
    When I explain November spending with an unrelated history filter
    Then the explanation receives only my November expense aggregates
    And the details show the exact monthly total and category share

  Scenario: Income-only months never call the provider
    Given I am signed in for monthly spending details
    And I have ten incomes and no expenses in November
    When I explain November spending with an unrelated history filter
    Then the details explain that there are no expenses to summarize

  Scenario: Invalid provider output offers a retry
    Given I am signed in for monthly spending details
    And I have nine incomes and one expense in November
    When the November explanation provider returns no valid observations
    Then the details offer a safe failure and an explicit retry

  Scenario: Explain directly from the dashboard in one action
    Given I am signed in for monthly spending details
    And I have nine incomes and one expense in November
    When I submit the dashboard Explain my spending action
    Then the explanation receives only my November expense aggregates
    And the details show a generated summary without another generation button

  Scenario: Provider reasoning metadata and valid comma punctuation are supported
    Given I am signed in for monthly spending details
    And I have nine incomes and one expense in November
    When the provider returns reasoning followed by a comma-punctuated summary
    Then the details show the comma-punctuated spending observation

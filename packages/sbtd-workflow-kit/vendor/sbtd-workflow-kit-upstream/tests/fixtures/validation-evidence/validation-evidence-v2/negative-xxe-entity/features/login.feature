Feature: login
  Scenario: registered user logs in
    Given a user
    When they login
    Then they see home

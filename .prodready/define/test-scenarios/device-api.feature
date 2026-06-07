Feature: Device API
  As a frontend operator
  I want to query discovered devices via REST API
  So that I can browse and inspect devices from the frontend

  Background:
    Given the REST API server is running
    And the following devices exist in the database:
      | chip_id | node      |
      | ABC123  | sensor-1  |
      | DEF456  | sensor-2  |
      | GHI789  | gateway-1 |

  Scenario: US-004 - List all devices with default pagination
    When I send GET /api/devices
    Then I receive a 200 response
    And the response contains all 3 devices
    And each device has id, chip_id, node, and created_at

  Scenario: US-004 - List devices with custom pagination
    When I send GET /api/devices?skip=1&limit=1
    Then I receive a 200 response
    And the response contains at most 1 device
    And the first device in the result is not the first device in the database

  Scenario: US-004 - List devices when database is empty
    Given no devices exist in the database
    When I send GET /api/devices
    Then I receive a 200 response
    And the response contains an empty array

  Scenario: US-004 - Limit parameter exceeds maximum
    When I send GET /api/devices?limit=1001
    Then I receive a 422 response

  Scenario: US-005 - Get single existing device
    Given a device with id 1 exists
    When I send GET /api/devices/1
    Then I receive a 200 response
    And the response contains the device with id, chip_id, node, and created_at

  Scenario: US-005 - Get non-existent device
    When I send GET /api/devices/9999
    Then I receive a 404 response

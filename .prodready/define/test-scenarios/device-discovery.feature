Feature: Device Discovery
  As a device discovery service
  I want to discover and deduplicate IoT devices from incoming messages
  So that the database contains only unique device records

  Background:
    Given the device discovery service is running
    And the database is empty

  Scenario: US-001 - Process valid message and store new device
    Given a device with chip_id "ABC123" and node "sensor-1" does not exist
    When a message arrives with chip_id "ABC123" and node "sensor-1"
    Then a new device record is created with chip_id "ABC123" and node "sensor-1"
    And the pair ("ABC123", "sensor-1") is added to the in-memory cache

  Scenario: US-001 - Skip message with missing chip_id
    Given a message arrives with only node "sensor-1" (no chip_id)
    When the handler processes the message
    Then no device record is created
    And the message is logged as invalid

  Scenario: US-001 - Skip message with missing node
    Given a message arrives with only chip_id "ABC123" (no node)
    When the handler processes the message
    Then no device record is created
    And the message is logged as invalid

  Scenario: US-001 - Skip None message
    Given a None message arrives
    When the handler processes it
    Then no exception is raised
    And no device record is created

  Scenario: US-002 - Cache hit prevents DB query
    Given a device with chip_id "ABC123" and node "sensor-1" is in the cache
    When a message arrives with chip_id "ABC123" and node "sensor-1"
    Then no database query is executed
    And no new device record is created

  Scenario: US-002 - Cache miss triggers DB check
    Given a device with chip_id "ABC123" and node "sensor-1" exists in DB but not in cache
    When a message arrives with chip_id "ABC123" and node "sensor-1"
    Then the database is queried
    And no new record is inserted
    And the pair is added to the cache

  Scenario: US-003 - DB unique constraint prevents duplicates
    Given a device with chip_id "ABC123" and node "sensor-1" exists in DB
    And the cache is empty (cold start)
    When a message arrives with chip_id "ABC123" and node "sensor-1"
    Then no new record is created
    And no unhandled exception occurs

  Scenario: US-003 - Same chip_id different node creates separate device
    Given a device with chip_id "ABC123" and node "sensor-1" exists in DB
    When a message arrives with chip_id "ABC123" and node "sensor-2"
    Then a new device record is created with chip_id "ABC123" and node "sensor-2"

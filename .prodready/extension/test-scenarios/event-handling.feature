Feature: Event Data Collection
  As a device discovery service
  I want to capture and store special event payloads from IoT devices
  So that the operator can monitor device health and file integrity

  Background:
    Given a device with chip_id "chip-001" and node "node-living" exists in the database

  Scenario: US-007 - Route system.pong event
    Given an incoming message with event "system.pong" and parameters {"heap_free": 61152, "build": "v1.22.1"}
    When the message handler processes it
    Then the event is queued for storage
    And the device discovery tuple (chip_id, node) is also queued

  Scenario: US-007 - Route system.microplate.hash event
    Given an incoming message with event "system.microplate.hash" and parameters {"file1.bin": "abc123"}
    When the message handler processes it
    Then the event is queued for storage

  Scenario: US-007 - Route system.userspace.hash event
    Given an incoming message with event "system.userspace.hash" and parameters {"main.py": "def456"}
    When the message handler processes it
    Then the event is queued for storage

  Scenario: US-007 - Ignore unrecognized event
    Given an incoming message with event "system.unknown" and parameters {}
    When the message handler processes it
    Then no event is queued for storage
    And device discovery proceeds normally

  Scenario: US-008 - Upsert new event type
    Given no DeviceEvent exists for device "chip-001" and event_type "system.pong"
    When a system.pong event with parameters {"heap_free": 61152} is processed
    Then a new DeviceEvent record is created with the parameters

  Scenario: US-008 - Overwrite existing event
    Given a DeviceEvent exists for device "chip-001" and event_type "system.pong" with parameters {"heap_free": 50000}
    When a new system.pong event with parameters {"heap_free": 61152} is processed
    Then the existing DeviceEvent record is updated with the new parameters
    And only one DeviceEvent record exists for that device and event_type

  Scenario: US-009 - Auto-create device on first event
    Given no device exists with chip_id "chip-new" and node "node-new"
    When a system.pong event arrives for chip_id "chip-new" and node "node-new"
    Then a new Device record is created
    And the DeviceEvent record is stored linked to the new device

  Scenario: US-012 - Worker handles DB error gracefully
    Given the database is unreachable
    When an event is processed by the worker
    Then the error is logged
    And the worker continues processing

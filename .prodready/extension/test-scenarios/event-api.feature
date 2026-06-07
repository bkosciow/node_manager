Feature: Event Data REST API
  As a frontend operator
  I want to retrieve event data for devices
  So that I can view device health and file integrity

  Background:
    Given a device with id 1 exists
    And a DeviceEvent exists for device 1 with event_type "system.pong" and parameters {"heap_free": 61152, "platform": "esp32"}
    And a DeviceEvent exists for device 1 with event_type "system.microplate.hash" and parameters {"file1.bin": "abc123"}

  Scenario: US-010 - Get specific event data
    Given device 1 has a stored system.pong event
    When I GET "/api/devices/1/events/system.pong"
    Then the response status is 200
    And the response body is {"heap_free": 61152, "platform": "esp32"}

  Scenario: US-010 - Event type not found
    Given device 1 has no stored event for "system.userspace.hash"
    When I GET "/api/devices/1/events/system.userspace.hash"
    Then the response status is 404

  Scenario: US-010 - Device not found
    When I GET "/api/devices/9999/events/system.pong"
    Then the response status is 404

  Scenario: US-010 - Invalid event type
    When I GET "/api/devices/1/events/invalid.event"
    Then the response status is 400

  Scenario: US-011 - Get all events for a device
    Given device 1 has two stored event types
    When I GET "/api/devices/1/events"
    Then the response status is 200
    And the response body is {"system.pong": {"heap_free": 61152, "platform": "esp32"}, "system.microplate.hash": {"file1.bin": "abc123"}}

  Scenario: US-011 - No events for a device
    Given a device with id 2 exists and has no stored events
    When I GET "/api/devices/2/events"
    Then the response status is 200
    And the response body is {}

  Scenario: US-011 - Device not found for all events
    When I GET "/api/devices/9999/events"
    Then the response status is 404

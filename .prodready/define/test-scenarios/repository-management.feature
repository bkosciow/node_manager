Feature: Repository Management
  As a system operator
  I want to manage software repositories and assign them to nodes
  So that I can track file versions and know which software each node should run

  Background:
    Given the repository management service is running
    And the database is empty

  Scenario: US-007 - Scan repo and store file hashes
    Given the /upgrades directory contains repo "node_north" with _microplate subfolder
    And the _microplate subfolder contains file "core.py"
    When the scanner script runs
    Then a Repository record is created with name "node_north" and type "microplate"
    And a RepositoryFile record is created with filename "core.py" and its SHA256 hash

  Scenario: US-007 - Scanner removes deleted file records
    Given a RepositoryFile record exists for filename "old.py" in repo "node_north"
    And the file "old.py" no longer exists on disk
    When the scanner script runs
    Then the RepositoryFile record for "old.py" is removed from the database

  Scenario: US-007 - Scanner handles unreadable file gracefully
    Given a file exists in a repo folder but is unreadable
    When the scanner script runs
    Then the error is logged
    And the scanner continues processing remaining files without crashing

  Scenario: US-008 - List repos by type
    Given repos exist in the database with types "microplate" and "userspace"
    When I send GET /api/repos?type=microplate
    Then I receive a 200 response
    And the response contains only microplate repos with their files and SHA256 hashes

  Scenario: US-008 - List repos with no matches
    Given no repos of type "userspace" exist
    When I send GET /api/repos?type=userspace
    Then I receive a 200 response
    And the response contains an empty list

  Scenario: US-008 - Invalid repo type
    When I send GET /api/repos?type=invalid
    Then I receive a 400 response

  Scenario: US-009 - Assign repo to node
    Given a device with id 1 exists
    And a repository with id 1 and type "microplate" exists
    When I assign repo 1 to device 1
    Then a NodeRepository record is created linking device 1 to repo 1

  Scenario: US-009 - Replace existing repo assignment
    Given device 1 has microplate repo 1 assigned
    When I assign microplate repo 2 to device 1
    Then the old assignment to repo 1 is removed
    And the new assignment to repo 2 is stored

  Scenario: US-009 - Assign second repo type to same node
    Given device 1 has microplate repo 1 assigned
    And userspace repo 2 exists
    When I assign userspace repo 2 to device 1
    Then device 1 now has both microplate and userspace repos assigned

  Scenario: US-009 - Assign non-existent repo
    Given device 1 exists
    And repo 9999 does not exist
    When I attempt to assign repo 9999 to device 1
    Then I receive a 404 response

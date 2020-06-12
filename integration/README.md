# Integration Tests

Contains integration tests that require a GCP environment set up with the right
service account credentials. These tests do not run automatically by simply
calling `py.test` - only the unit tests in the directories specified in
`pytest.ini`. To run these tests simply execute `./integration/run.sh`

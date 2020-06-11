# Integration Tests

Contains integration tests that require a GCP environment set up with the right
service account credentials. These tests do not run automatically by simply
calling `py.test` - only the unit tests in the directories specified in
`pytest.ini`. To run these tests, please specify the path to this directory
or test(s) explicitly, e.g.

```sh
py.test integration --log-cli-level=INFO
py.test integration/test_machines.py --log-cli-level=INFO
py.test integration/test_machines.py integration/test_templates.py --log-cli-level=INFO
```

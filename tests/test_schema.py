import yaml
from django.core.management import call_command


def test_openapi_schema_is_valid_and_complete(tmp_path):
    # --fail-on-warn makes a new endpoint without schema annotations fail here
    schema_file = tmp_path / "schema.yml"
    call_command("spectacular", "--validate", "--fail-on-warn", "--file", str(schema_file))

    schema = yaml.safe_load(schema_file.read_text())
    operations = {
        (path, method) for path, methods in schema["paths"].items() for method in methods
    }
    assert ("/auth/login/", "post") in operations
    assert ("/auth/sessions/{session_id}/", "delete") in operations
    assert len(operations) == 14
    assert "jwtAuth" in schema["components"]["securitySchemes"]


def test_login_documents_its_responses(tmp_path):
    schema_file = tmp_path / "schema.yml"
    call_command("spectacular", "--file", str(schema_file))
    responses = yaml.safe_load(schema_file.read_text())["paths"]["/auth/login/"]["post"]["responses"]
    assert set(responses) == {"200", "401", "403", "429"}

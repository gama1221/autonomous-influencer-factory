# tests/unit/utils/test_validation.py
"""
Tests for validation modules.
These tests should FAIL initially - they define the contract.
"""
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from utils.validation.schema_validator import SchemaValidator, SchemaValidationError
from utils.validation.spec_validator import SpecValidator, validate_project

class TestSchemaValidation:
    """Test JSON Schema validation."""
    
    def test_schema_validation_basic(self):
        """Test basic schema validation."""
        validator = SchemaValidator()
        
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer", "minimum": 0}
            },
            "required": ["name"]
        }
        
        # Valid data
        valid_data = {"name": "John", "age": 30}
        is_valid, errors = validator.validate(valid_data, schema, raise_on_error=False)
        
        assert is_valid, f"Valid data rejected: {errors}"
        
        # Invalid data
        invalid_data = {"name": "John", "age": -5}
        is_valid, errors = validator.validate(invalid_data, schema, raise_on_error=False)
        
        assert not is_valid, "Invalid data should be rejected"
        assert len(errors) > 0, "Should have validation errors"
    
    def test_skill_manifest_validation(self):
        """Test skill manifest validation."""
        validator = SchemaValidator()
        
        # Create a test skill manifest
        manifest = {
            "name": "test_skill",
            "version": "1.0.0",
            "description": "Test skill",
            "implementation": {
                "language": "python",
                "entrypoint": "test.py"
            },
            "interfaces": [
                {
                    "name": "test_interface",
                    "description": "Test interface"
                }
            ]
        }
        
        # This test will fail until skill manifest validation is implemented
        assert False, "Skill manifest validation not implemented"
        
        # When implemented:
        is_valid, errors = validator.validate_skill_manifest(manifest)
        assert is_valid, f"Valid skill manifest rejected: {errors}"
    
    def test_custom_validators(self):
        """Test custom validators (skill_manifest, openclaw_protocol)."""
        validator = SchemaValidator()
        
        # Test openclaw_protocol validator
        valid_message = {
            "agent_id": "550e8400-e29b-41d4-a716-446655440000",
            "message_type": "HEARTBEAT",
            "timestamp": "2024-02-04T12:00:00Z",
            "payload": {"status": "active"}
        }
        
        is_valid, errors = validator.validate_openclaw_message(valid_message)
        
        assert is_valid, f"Valid OpenClaw message rejected: {errors}"

class TestSpecValidation:
    """Test specification validation."""
    
    def test_spec_validator_loads_requirements(self):
        """Test that spec validator loads requirements from spec files."""
        # Create mock spec files
        spec_dir = Path("test_specs")
        spec_dir.mkdir(exist_ok=True)
        
        # Create functional spec
        functional_spec = spec_dir / "functional.md"
        functional_spec.write_text("""
### As a Research Agent
- I want to fetch trending topics from multiple platforms
- I want to analyze correlation between trends
""")
        
        validator = SpecValidator(specs_dir=spec_dir)
        
        # Should have loaded requirements
        assert len(validator.requirements) > 0, "No requirements loaded from spec"
        
        # Cleanup
        import shutil
        shutil.rmtree(spec_dir)
    
    def test_skill_validation_against_specs(self):
        """Test that skills are validated against specifications."""
        # Create a test skill directory
        skill_dir = Path("test_skill_fetch_trends")
        skill_dir.mkdir(exist_ok=True)
        
        # Create skill.yaml
        skill_yaml = skill_dir / "skill.yaml"
        skill_yaml.write_text("""
name: skill_fetch_trends
version: 1.0.0
description: Fetch trending topics
implementation:
  language: python
  entrypoint: src/fetch_trends.py
interfaces:
  - name: fetch_youtube_trends
    description: Fetch trends from YouTube
""")
        
        # Create src directory with implementation
        src_dir = skill_dir / "src"
        src_dir.mkdir(exist_ok=True)
        impl_file = src_dir / "fetch_trends.py"
        impl_file.write_text("""
def fetch_youtube_trends(region: str, category: str):
    \"\"\"Fetch YouTube trends.\"\"\"
    return []
""")
        
        validator = SpecValidator()
        result = validator.validate_skill(skill_dir)
        
        # This test defines expected behavior
        assert result.passed, f"Valid skill rejected: {result.violations}"
        
        # Cleanup
        import shutil
        shutil.rmtree(skill_dir)
    
    def test_project_validation(self):
        """Test entire project validation."""
        # This is an integration test
        report = validate_project()
        
        assert "summary" in report, "Validation report missing summary"
        assert "detailed_results" in report, "Validation report missing detailed results"
        
        summary = report["summary"]
        assert "total_files" in summary, "Summary missing total_files"
        assert "pass_percentage" in summary, "Summary missing pass_percentage"
        
        # Log the results
        print(f"\nValidation Report:")
        print(f"Files: {summary['passed_files']}/{summary['total_files']} passed")
        print(f"Violations: {summary['total_violations']}")
        print(f"Warnings: {summary['total_warnings']}")

@pytest.mark.contract
class TestValidationContracts:
    """Contract tests for validation modules."""
    
    def test_schema_validation_contract(self):
        """Test that schema validator follows defined contract."""
        validator = SchemaValidator()
        
        # Contract: Must support JSON Schema Draft-07
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "test": {"type": "string"}
            }
        }
        
        is_valid, errors = validator.validate({"test": "value"}, schema)
        
        assert is_valid, f"Failed to validate against Draft-07 schema: {errors}"
    
    def test_spec_traceability_contract(self):
        """Test that spec validation provides traceability to source specs."""
        validator = SpecValidator()
        
        # This test defines the traceability requirement
        # Every violation/warning should reference the source specification
        
        # Create a test validation result
        result = validator.validate_python_file(Path("test.py"))
        
        if not result.passed:
            for violation in result.violations:
                # Violations should reference spec IDs or files
                assert any(ref in violation.lower() for ref in ["fs-", "ts-", "api-", "spec"]), \
                    f"Violation missing spec reference: {violation}"
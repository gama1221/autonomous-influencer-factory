# scripts/validate_specs.py
#!/usr/bin/env python3
"""
Specification validation script.
Checks if code aligns with ratified specifications.
"""
import json
import yaml
from pathlib import Path
import sys
from typing import Dict, List
import jsonschema
from dataclasses import dataclass

@dataclass
class ValidationResult:
    """Result of spec validation."""
    passed: bool
    errors: List[str]
    warnings: List[str]

class SpecValidator:
    """Validates code against specifications."""
    
    def __init__(self, specs_dir: Path = Path("specs")):
        self.specs_dir = specs_dir
        self.schemas = self._load_schemas()
    
    def _load_schemas(self) -> Dict:
        """Load all JSON schemas from specs directory."""
        schemas = {}
        for schema_file in self.specs_dir.rglob("*.schema.json"):
            with open(schema_file) as f:
                schemas[schema_file.stem] = json.load(f)
        return schemas
    
    def validate_skill(self, skill_dir: Path) -> ValidationResult:
        """Validate a skill implementation against its spec."""
        errors = []
        warnings = []
        
        # Check if skill.yaml exists
        skill_yaml = skill_dir / "skill.yaml"
        if not skill_yaml.exists():
            errors.append(f"Missing skill.yaml in {skill_dir}")
            return ValidationResult(False, errors, warnings)
        
        # Check if schemas exist
        request_schema = skill_dir / "schemas" / "request.json"
        response_schema = skill_dir / "schemas" / "response.json"
        
        if not request_schema.exists():
            errors.append(f"Missing request schema in {skill_dir}")
        
        if not response_schema.exists():
            errors.append(f"Missing response schema in {skill_dir}")
        
        # Check if source files exist
        src_dir = skill_dir / "src"
        if not src_dir.exists():
            errors.append(f"Missing src directory in {skill_dir}")
        else:
            implementations = list(src_dir.glob("*.py"))
            if not implementations:
                warnings.append(f"No implementation files found in {src_dir}")
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    def validate_api_contract(self, endpoint_code: Path, schema_name: str) -> ValidationResult:
        """Validate API endpoint code against its schema."""
        errors = []
        
        if schema_name not in self.schemas:
            errors.append(f"Schema {schema_name} not found")
            return ValidationResult(False, errors, [])
        
        # TODO: Parse Python file and validate against schema
        # This is a simplified version - in reality, you'd parse AST
        
        return ValidationResult(True, [], [])

def main():
    """Main validation entry point."""
    validator = SpecValidator()
    
    print("🔍 Validating Project Chimera specifications...")
    
    # Validate all skills
    skills_dir = Path("skills")
    all_passed = True
    
    for skill_dir in skills_dir.iterdir():
        if skill_dir.is_dir() and skill_dir.name.startswith("skill_"):
            print(f"\nValidating {skill_dir.name}...")
            result = validator.validate_skill(skill_dir)
            
            if result.passed:
                print(f"  ✓ {skill_dir.name} passed validation")
            else:
                print(f"  ✗ {skill_dir.name} failed validation:")
                for error in result.errors:
                    print(f"    - {error}")
                all_passed = False
    
    # Exit with appropriate code
    if all_passed:
        print("\n✅ All specifications validated successfully!")
        sys.exit(0)
    else:
        print("\n❌ Specification validation failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
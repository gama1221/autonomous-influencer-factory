# utils/validation/spec_validator.py
"""
Specification validation for Project Chimera.
Validates that code aligns with ratified specifications.
"""
import ast
import inspect
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
import json
import yaml
from dataclasses import dataclass

from ..logging import get_logger, log_execution
from .schema_validator import SchemaValidator, SchemaValidationError

logger = get_logger("validation.spec")

@dataclass
class ValidationResult:
    """Result of specification validation."""
    passed: bool
    violations: List[str]
    warnings: List[str]
    spec_file: Optional[Path] = None
    code_file: Optional[Path] = None

@dataclass  
class SpecRequirement:
    """A requirement from a specification."""
    id: str
    description: str
    type: str  # "function", "class", "api_endpoint", "skill"
    constraints: Dict[str, Any]
    source_spec: Path

class SpecValidator:
    """Validates code against ratified specifications."""
    
    def __init__(self, specs_dir: Path = Path("specs")):
        self.specs_dir = specs_dir
        self.schema_validator = SchemaValidator()
        self.requirements: Dict[str, SpecRequirement] = {}
        self._load_requirements()
    
    def _load_requirements(self) -> None:
        """Load requirements from specification files."""
        # Load from functional spec
        functional_spec = self.specs_dir / "functional.md"
        if functional_spec.exists():
            self._parse_functional_spec(functional_spec)
        
        # Load from technical spec
        technical_spec = self.specs_dir / "technical.md"
        if technical_spec.exists():
            self._parse_technical_spec(technical_spec)
        
        # Load from API schemas
        api_dir = self.specs_dir / "api"
        if api_dir.exists():
            self._parse_api_schemas(api_dir)
    
    def _parse_functional_spec(self, spec_file: Path) -> None:
        """Parse functional specification for requirements."""
        try:
            content = spec_file.read_text()
            
            # Parse user stories (simplified parsing)
            lines = content.split('\n')
            current_story = None
            
            for i, line in enumerate(lines):
                line = line.strip()
                
                if line.startswith('### As a'):
                    # New user story
                    current_story = line
                elif line.startswith('- I ') and current_story:
                    # Requirement within user story
                    req_id = f"FS-{i+1:03d}"
                    desc = line[2:]  # Remove "- "
                    
                    # Extract requirement type
                    if 'fetch' in desc.lower() or 'retrieve' in desc.lower():
                        req_type = "skill"
                    elif 'generate' in desc.lower() or 'create' in desc.lower():
                        req_type = "skill"
                    elif 'monitor' in desc.lower() or 'analyze' in desc.lower():
                        req_type = "skill"
                    else:
                        req_type = "function"
                    
                    self.requirements[req_id] = SpecRequirement(
                        id=req_id,
                        description=desc,
                        type=req_type,
                        constraints={"source": current_story},
                        source_spec=spec_file
                    )
                    
                    logger.debug(f"Loaded requirement {req_id}: {desc}")
        
        except Exception as e:
            logger.error(f"Failed to parse functional spec: {e}")
    
    def _parse_technical_spec(self, spec_file: Path) -> None:
        """Parse technical specification for requirements."""
        try:
            content = spec_file.read_text()
            
            # Look for API contracts
            if '### API Contracts' in content:
                # This is a simplified parse - in reality you'd use proper parsing
                sections = content.split('### API Contracts')[1].split('###')[0]
                
                # Look for JSON examples
                lines = sections.split('\n')
                in_json = False
                json_content = []
                
                for i, line in enumerate(lines):
                    if '```json' in line:
                        in_json = True
                        json_content = []
                    elif '```' in line and in_json:
                        in_json = False
                        
                        try:
                            json_data = json.loads('\n'.join(json_content))
                            req_id = f"TS-API-{i+1:03d}"
                            
                            self.requirements[req_id] = SpecRequirement(
                                id=req_id,
                                description=f"API Contract: {json_data.get('title', 'unnamed')}",
                                type="api_endpoint",
                                constraints={"schema": json_data},
                                source_spec=spec_file
                            )
                            
                            logger.debug(f"Loaded API requirement {req_id}")
                            
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse JSON in technical spec: {e}")
                        
                    elif in_json:
                        json_content.append(line)
        
        except Exception as e:
            logger.error(f"Failed to parse technical spec: {e}")
    
    def _parse_api_schemas(self, api_dir: Path) -> None:
        """Parse API schemas for requirements."""
        for schema_file in api_dir.glob("*.schema.json"):
            try:
                with open(schema_file, 'r') as f:
                    schema = json.load(f)
                
                req_id = f"API-{schema_file.stem.upper()}"
                
                self.requirements[req_id] = SpecRequirement(
                    id=req_id,
                    description=f"API Schema: {schema.get('title', schema_file.stem)}",
                    type="api_endpoint",
                    constraints={"schema": schema},
                    source_spec=schema_file
                )
                
                logger.debug(f"Loaded API schema requirement {req_id}")
                
            except Exception as e:
                logger.error(f"Failed to parse API schema {schema_file}: {e}")
    
    @log_execution(logger_name="validation.spec")
    def validate_skill(self, skill_dir: Path) -> ValidationResult:
        """Validate a skill implementation against specifications."""
        violations = []
        warnings = []
        
        # Check skill structure
        skill_yaml = skill_dir / "skill.yaml"
        if not skill_yaml.exists():
            violations.append(f"Missing skill.yaml in {skill_dir}")
            return ValidationResult(False, violations, warnings, code_file=skill_dir)
        
        try:
            with open(skill_yaml, 'r') as f:
                skill_config = yaml.safe_load(f)
            
            # Validate skill manifest
            is_valid, errors = self.schema_validator.validate_skill_manifest(skill_yaml)
            if not is_valid:
                violations.extend(errors)
            
            # Check for required sections
            required_sections = ["name", "description", "implementation", "interfaces"]
            for section in required_sections:
                if section not in skill_config:
                    violations.append(f"Missing required section in skill.yaml: {section}")
            
            # Validate interfaces against specs
            if "interfaces" in skill_config:
                for interface in skill_config["interfaces"]:
                    # Check if this interface fulfills a requirement
                    interface_name = interface.get("name", "")
                    matching_reqs = [
                        req for req in self.requirements.values()
                        if interface_name.lower() in req.description.lower()
                        and req.type == "skill"
                    ]
                    
                    if not matching_reqs:
                        warnings.append(f"Interface '{interface_name}' not explicitly required by specs")
                    else:
                        logger.debug(f"Interface '{interface_name}' matches requirement: {matching_reqs[0].id}")
            
            # Check for implementation files
            src_dir = skill_dir / "src"
            if not src_dir.exists():
                violations.append(f"Missing src directory in {skill_dir}")
            else:
                impl_files = list(src_dir.glob("*.py"))
                if not impl_files:
                    violations.append(f"No Python implementation files in {src_dir}")
                
                # Validate each implementation file
                for impl_file in impl_files:
                    file_result = self.validate_python_file(impl_file)
                    if not file_result.passed:
                        violations.extend(file_result.violations)
                    warnings.extend(file_result.warnings)
            
            # Check for tests
            tests_dir = skill_dir / "tests"
            if not tests_dir.exists():
                warnings.append(f"No tests directory in {skill_dir}")
            else:
                test_files = list(tests_dir.glob("test_*.py"))
                if not test_files:
                    warnings.append(f"No test files in {tests_dir}")
        
        except Exception as e:
            violations.append(f"Failed to validate skill: {e}")
        
        return ValidationResult(
            passed=len(violations) == 0,
            violations=violations,
            warnings=warnings,
            code_file=skill_dir
        )
    
    @log_execution(logger_name="validation.spec")
    def validate_python_file(self, file_path: Path) -> ValidationResult:
        """Validate a Python file against specifications."""
        violations = []
        warnings = []
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Parse AST
            tree = ast.parse(content)
            
            # Find all function definitions
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_name = node.name
                    
                    # Check if function matches a requirement
                    matching_reqs = [
                        req for req in self.requirements.values()
                        if func_name.lower() in req.description.lower() 
                        or req.description.lower() in func_name.lower()
                    ]
                    
                    if matching_reqs:
                        logger.debug(f"Function '{func_name}' matches requirement: {matching_reqs[0].id}")
                        
                        # Validate function signature against constraints
                        if "schema" in matching_reqs[0].constraints:
                            # Check if function has proper type hints
                            if not node.args.args:
                                warnings.append(f"Function '{func_name}' has no parameters")
                            
                            # Check for docstring
                            if not ast.get_docstring(node):
                                warnings.append(f"Function '{func_name}' has no docstring")
                    
                    elif not func_name.startswith('_'):
                        # Public function not matching any requirement
                        warnings.append(f"Function '{func_name}' not explicitly required by specs")
                
                elif isinstance(node, ast.ClassDef):
                    class_name = node.name
                    
                    # Check for docstring in classes
                    if not ast.get_docstring(node):
                        warnings.append(f"Class '{class_name}' has no docstring")
        
        except SyntaxError as e:
            violations.append(f"Syntax error in {file_path}: {e}")
        except Exception as e:
            violations.append(f"Failed to parse {file_path}: {e}")
        
        return ValidationResult(
            passed=len(violations) == 0,
            violations=violations,
            warnings=warnings,
            code_file=file_path
        )
    
    @log_execution(logger_name="validation.spec")  
    def validate_api_endpoint(self, endpoint_file: Path) -> ValidationResult:
        """Validate an API endpoint against specifications."""
        violations = []
        warnings = []
        
        try:
            with open(endpoint_file, 'r') as f:
                content = f.read()
            
            # Parse for FastAPI/Starlette decorators
            lines = content.split('\n')
            
            for i, line in enumerate(lines):
                line = line.strip()
                
                # Look for route decorators
                if line.startswith('@') and any(method in line for method in ['post', 'get', 'put', 'delete']):
                    # Extract endpoint path
                    next_line = lines[i + 1] if i + 1 < len(lines) else ""
                    if 'def ' in next_line:
                        func_name = next_line.split('def ')[1].split('(')[0]
                        
                        # Check if this endpoint has a schema requirement
                        matching_reqs = [
                            req for req in self.requirements.values()
                            if req.type == "api_endpoint"
                            and (func_name in req.description or req.id in func_name)
                        ]
                        
                        if matching_reqs:
                            req = matching_reqs[0]
                            logger.debug(f"Endpoint '{func_name}' matches requirement: {req.id}")
                            
                            # Check for request/response model usage
                            if "schema" in req.constraints:
                                schema = req.constraints["schema"]
                                
                                # Look for Pydantic model usage
                                model_used = False
                                for j in range(i, min(i + 10, len(lines))):
                                    if any(keyword in lines[j] for keyword in ['Request', 'Response', 'Model']):
                                        model_used = True
                                        break
                                
                                if not model_used:
                                    violations.append(
                                        f"Endpoint '{func_name}' should use Pydantic models matching schema: {req.id}"
                                    )
                        
                        else:
                            warnings.append(f"API endpoint '{func_name}' not explicitly required by specs")
        
        except Exception as e:
            violations.append(f"Failed to validate API endpoint: {e}")
        
        return ValidationResult(
            passed=len(violations) == 0,
            violations=violations,
            warnings=warnings,
            code_file=endpoint_file
        )
    
    @log_execution(logger_name="validation.spec")
    def validate_directory(self, directory: Path, recursive: bool = True) -> List[ValidationResult]:
        """Validate all files in a directory against specifications."""
        results = []
        
        if not directory.exists():
            logger.error(f"Directory not found: {directory}")
            return results
        
        # Define validation patterns
        skill_pattern = "skill_*"
        api_pattern = "*endpoint*.py"
        python_pattern = "*.py"
        
        # Validate skills
        for skill_dir in directory.glob(skill_pattern):
            if skill_dir.is_dir():
                result = self.validate_skill(skill_dir)
                results.append(result)
        
        # Validate Python files
        if recursive:
            python_files = directory.rglob(python_pattern)
        else:
            python_files = directory.glob(python_pattern)
        
        for python_file in python_files:
            # Skip files in skill directories (already validated)
            if any(part.startswith("skill_") for part in python_file.parts):
                continue
            
            # Skip test files
            if "test_" in python_file.name or python_file.parent.name == "tests":
                continue
            
            # Validate based on file type
            if "api" in python_file.parts or "endpoint" in python_file.stem:
                result = self.validate_api_endpoint(python_file)
            else:
                result = self.validate_python_file(python_file)
            
            results.append(result)
        
        return results
    
    def generate_validation_report(self, results: List[ValidationResult]) -> Dict[str, Any]:
        """Generate a comprehensive validation report."""
        total_files = len(results)
        passed_files = sum(1 for r in results if r.passed)
        total_violations = sum(len(r.violations) for r in results)
        total_warnings = sum(len(r.warnings) for r in results)
        
        # Group by file type
        by_type = {}
        for result in results:
            if result.code_file:
                file_type = self._classify_file_type(result.code_file)
                if file_type not in by_type:
                    by_type[file_type] = []
                by_type[file_type].append(result)
        
        # Detailed results
        detailed_results = []
        for result in results:
            if result.code_file:
                detailed_results.append({
                    "file": str(result.code_file),
                    "passed": result.passed,
                    "violations": result.violations,
                    "warnings": result.warnings,
                    "spec_file": str(result.spec_file) if result.spec_file else None
                })
        
        report = {
            "summary": {
                "total_files": total_files,
                "passed_files": passed_files,
                "failed_files": total_files - passed_files,
                "pass_percentage": (passed_files / total_files * 100) if total_files > 0 else 0,
                "total_violations": total_violations,
                "total_warnings": total_warnings
            },
            "by_file_type": {
                file_type: {
                    "count": len(results),
                    "passed": sum(1 for r in results if r.passed),
                    "violations": sum(len(r.violations) for r in results),
                    "warnings": sum(len(r.warnings) for r in results)
                }
                for file_type, results in by_type.items()
            },
            "detailed_results": detailed_results,
            "unfulfilled_requirements": self._find_unfulfilled_requirements(results),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return report
    
    def _classify_file_type(self, file_path: Path) -> str:
        """Classify a file by type."""
        if file_path.is_dir() and file_path.name.startswith("skill_"):
            return "skill"
        elif file_path.suffix == ".py":
            if "api" in file_path.parts or "endpoint" in file_path.stem:
                return "api"
            elif "test" in file_path.name or file_path.parent.name == "tests":
                return "test"
            else:
                return "module"
        else:
            return "other"
    
    def _find_unfulfilled_requirements(self, results: List[ValidationResult]) -> List[Dict[str, Any]]:
        """Find requirements that are not fulfilled by any code."""
        # This is a simplified implementation
        # In reality, you'd need to map requirements to specific code files
        
        unfulfilled = []
        
        for req_id, requirement in self.requirements.items():
            # Check if this requirement is mentioned in any validation result
            mentioned = False
            for result in results:
                for violation in result.violations:
                    if req_id in violation:
                        mentioned = True
                        break
                if mentioned:
                    break
            
            if not mentioned and requirement.type in ["skill", "api_endpoint", "function"]:
                unfulfilled.append({
                    "id": req_id,
                    "description": requirement.description,
                    "type": requirement.type,
                    "source_spec": str(requirement.source_spec)
                })
        
        return unfulfilled

# Global validator instance
_spec_validator_instance = None

def get_spec_validator(specs_dir: Optional[Path] = None) -> SpecValidator:
    """Get the global spec validator instance."""
    global _spec_validator_instance
    if _spec_validator_instance is None:
        _spec_validator_instance = SpecValidator(specs_dir or Path("specs"))
    return _spec_validator_instance

def validate_project() -> Dict[str, Any]:
    """Validate the entire project against specifications."""
    validator = get_spec_validator()
    
    # Validate key directories
    results = []
    
    # Validate skills
    skills_dir = Path("skills")
    if skills_dir.exists():
        skill_results = validator.validate_directory(skills_dir)
        results.extend(skill_results)
    
    # Validate API
    api_dir = Path("api")
    if api_dir.exists():
        api_results = validator.validate_directory(api_dir, recursive=True)
        results.extend(api_results)
    
    # Validate agents
    agents_dir = Path("agents")
    if agents_dir.exists():
        agent_results = validator.validate_directory(agents_dir, recursive=True)
        results.extend(agent_results)
    
    # Generate report
    report = validator.generate_validation_report(results)
    
    # Log summary
    summary = report["summary"]
    logger.info(
        f"Spec validation completed: "
        f"{summary['passed_files']}/{summary['total_files']} files passed "
        f"({summary['pass_percentage']:.1f}%)"
    )
    
    if summary['total_violations'] > 0:
        logger.warning(f"Found {summary['total_violations']} specification violations")
    
    if summary['total_warnings'] > 0:
        logger.info(f"Found {summary['total_warnings']} warnings")
    
    return report
# utils/validation/schema_validator.py
"""
JSON Schema validation for Project Chimera.
"""
import json
import jsonschema
from jsonschema import Draft7Validator, ValidationError
from typing import Any, Dict, List, Optional, Union, Tuple
from pathlib import Path
import yaml

from ..logging import get_logger, log_execution

logger = get_logger("validation.schema")

class SchemaValidationError(Exception):
    """Custom exception for schema validation errors."""
    
    def __init__(self, message: str, errors: List[str] = None):
        super().__init__(message)
        self.errors = errors or []
        self.message = message
    
    def __str__(self) -> str:
        if self.errors:
            return f"{self.message}\nErrors:\n" + "\n".join(f"- {e}" for e in self.errors)
        return self.message

class SchemaValidator:
    """JSON Schema validator with custom extensions."""
    
    def __init__(self):
        self.validators: Dict[str, Draft7Validator] = {}
        self.custom_validators: Dict[str, callable] = {}
        
        # Register custom validators
        self._register_custom_validators()
    
    def _register_custom_validators(self) -> None:
        """Register custom validators."""
        
        def validate_skill_manifest(validator, value, instance, schema):
            """Validate skill manifest structure."""
            if not isinstance(instance, dict):
                yield ValidationError(f"Skill manifest must be an object, got {type(instance)}")
                return
            
            required_fields = ["name", "version", "description", "implementation"]
            for field in required_fields:
                if field not in instance:
                    yield ValidationError(f"Missing required field: {field}")
            
            # Validate implementation section
            if "implementation" in instance:
                impl = instance["implementation"]
                if not isinstance(impl, dict):
                    yield ValidationError("implementation must be an object")
                elif "language" not in impl:
                    yield ValidationError("implementation.language is required")
                elif impl.get("language") != "python":
                    yield ValidationError("Only Python implementation is currently supported")
        
        def validate_openclaw_protocol(validator, value, instance, schema):
            """Validate OpenClaw protocol messages."""
            if not isinstance(instance, dict):
                yield ValidationError(f"OpenClaw message must be an object, got {type(instance)}")
                return
            
            required_fields = ["agent_id", "message_type", "timestamp", "payload"]
            for field in required_fields:
                if field not in instance:
                    yield ValidationError(f"Missing required field: {field}")
            
            # Validate timestamp format (ISO 8601)
            if "timestamp" in instance:
                import re
                timestamp_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$'
                if not re.match(timestamp_pattern, instance["timestamp"]):
                    yield ValidationError("timestamp must be in ISO 8601 format")
        
        self.custom_validators = {
            "skill_manifest": validate_skill_manifest,
            "openclaw_protocol": validate_openclaw_protocol
        }
    
    @log_execution(logger_name="validation", log_args=False)
    def load_schema(self, schema_path: Union[str, Path, Dict]) -> Dict[str, Any]:
        """Load a JSON schema from file or dictionary."""
        try:
            if isinstance(schema_path, dict):
                schema = schema_path
            elif isinstance(schema_path, (str, Path)):
                path = Path(schema_path)
                
                if not path.exists():
                    raise FileNotFoundError(f"Schema file not found: {path}")
                
                with open(path, 'r') as f:
                    if path.suffix in ['.yaml', '.yml']:
                        schema = yaml.safe_load(f)
                    else:
                        schema = json.load(f)
            else:
                raise ValueError(f"Invalid schema source type: {type(schema_path)}")
            
            # Validate that it's a valid JSON Schema
            jsonschema.Draft7Validator.check_schema(schema)
            
            # Create validator with custom validators
            validator = Draft7Validator(schema)
            
            # Add custom validators
            for format_name, format_validator in self.custom_validators.items():
                validator.format_checker.checks(format_name)(format_validator)
            
            # Store validator
            if isinstance(schema_path, (str, Path)):
                self.validators[str(schema_path)] = validator
            
            logger.debug(f"Loaded schema: {schema.get('title', 'unnamed')}")
            return schema
            
        except (json.JSONDecodeError, yaml.YAMLError) as e:
            logger.error(f"Failed to parse schema: {e}")
            raise SchemaValidationError(f"Invalid schema format: {e}")
        except jsonschema.SchemaError as e:
            logger.error(f"Invalid JSON Schema: {e}")
            raise SchemaValidationError(f"Invalid JSON Schema: {e}")
        except Exception as e:
            logger.error(f"Failed to load schema: {e}")
            raise
    
    @log_execution(logger_name="validation")
    def validate(
        self,
        data: Any,
        schema: Union[str, Path, Dict],
        raise_on_error: bool = True
    ) -> Tuple[bool, List[str]]:
        """
        Validate data against schema.
        
        Args:
            data: Data to validate
            schema: Schema to validate against
            raise_on_error: Whether to raise exception on validation failure
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        try:
            # Get or load validator
            if isinstance(schema, (str, Path)) and str(schema) in self.validators:
                validator = self.validators[str(schema)]
            else:
                schema_dict = self.load_schema(schema)
                validator = self.validators.get(str(schema)) or Draft7Validator(schema_dict)
            
            # Perform validation
            errors = list(validator.iter_errors(data))
            
            if errors:
                error_messages = []
                for error in errors:
                    # Build descriptive error message
                    if error.path:
                        path = ".".join(str(p) for p in error.path)
                        message = f"At '{path}': {error.message}"
                    else:
                        message = f"At root: {error.message}"
                    
                    # Add context if available
                    if error.context:
                        for sub_error in error.context:
                            if sub_error.path:
                                sub_path = ".".join(str(p) for p in sub_error.path)
                                message += f"\n  - At '{sub_path}': {sub_error.message}"
                            else:
                                message += f"\n  - {sub_error.message}"
                    
                    error_messages.append(message)
                    logger.debug(f"Validation error: {message}")
                
                if raise_on_error:
                    raise SchemaValidationError(
                        f"Schema validation failed with {len(errors)} error(s)",
                        error_messages
                    )
                
                return False, error_messages
            
            logger.debug("Validation successful")
            return True, []
            
        except SchemaValidationError:
            raise
        except Exception as e:
            error_msg = f"Unexpected error during validation: {e}"
            logger.error(error_msg, exc_info=True)
            
            if raise_on_error:
                raise SchemaValidationError(error_msg)
            
            return False, [error_msg]
    
    @log_execution(logger_name="validation")
    def validate_skill_manifest(self, manifest_path: Union[str, Path]) -> Tuple[bool, List[str]]:
        """Validate a skill manifest file."""
        try:
            path = Path(manifest_path)
            
            if not path.exists():
                return False, [f"Manifest file not found: {path}"]
            
            with open(path, 'r') as f:
                if path.suffix in ['.yaml', '.yml']:
                    manifest = yaml.safe_load(f)
                else:
                    manifest = json.load(f)
            
            # Load skill manifest schema
            schema_dir = Path(__file__).parent.parent.parent / "specs" / "api"
            schema_file = schema_dir / "skill_manifest.schema.json"
            
            if not schema_file.exists():
                # Create minimal schema for validation
                schema = {
                    "$schema": "http://json-schema.org/draft-07/schema#",
                    "title": "Skill Manifest Schema",
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "version": {"type": "string"},
                        "description": {"type": "string"},
                        "implementation": {
                            "type": "object",
                            "properties": {
                                "language": {"type": "string", "const": "python"}
                            },
                            "required": ["language"]
                        }
                    },
                    "required": ["name", "version", "description", "implementation"]
                }
            else:
                schema = self.load_schema(schema_file)
            
            return self.validate(manifest, schema, raise_on_error=False)
            
        except Exception as e:
            logger.error(f"Failed to validate skill manifest: {e}")
            return False, [str(e)]
    
    @log_execution(logger_name="validation")
    def validate_openclaw_message(self, message: Dict) -> Tuple[bool, List[str]]:
        """Validate an OpenClaw protocol message."""
        try:
            # Load OpenClaw message schema
            schema_dir = Path(__file__).parent.parent.parent / "specs" / "api"
            schema_file = schema_dir / "openclaw_message.schema.json"
            
            if not schema_file.exists():
                # Create minimal schema for validation
                schema = {
                    "$schema": "http://json-schema.org/draft-07/schema#",
                    "title": "OpenClaw Message Schema",
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "format": "uuid"},
                        "message_type": {
                            "type": "string",
                            "enum": ["HEARTBEAT", "STATUS_UPDATE", "CONTENT_PUBLISHED", "TREND_DETECTED"]
                        },
                        "timestamp": {"type": "string", "format": "date-time"},
                        "payload": {"type": "object"}
                    },
                    "required": ["agent_id", "message_type", "timestamp", "payload"],
                    "format": "openclaw_protocol"
                }
            else:
                schema = self.load_schema(schema_file)
            
            return self.validate(message, schema, raise_on_error=False)
            
        except Exception as e:
            logger.error(f"Failed to validate OpenClaw message: {e}")
            return False, [str(e)]
    
    def create_schema_from_spec(self, spec_type: str, **kwargs) -> Dict[str, Any]:
        """Create a JSON schema from a specification type."""
        schemas = {
            "trend_request": {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "title": "Trend Fetch Request",
                "type": "object",
                "properties": {
                    "platforms": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["youtube", "tiktok", "twitter", "reddit"]},
                        "minItems": 1
                    },
                    "time_range": {
                        "type": "string",
                        "enum": ["1h", "4h", "24h", "7d"],
                        "default": "24h"
                    },
                    "region": {"type": "string", "default": "global"},
                    "max_results_per_platform": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 10
                    }
                },
                "required": ["platforms"]
            },
            "content_generation": {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "title": "Content Generation Request",
                "type": "object",
                "properties": {
                    "trend_id": {"type": "string", "format": "uuid"},
                    "content_type": {
                        "type": "string",
                        "enum": ["tweet", "post", "video_script", "image_caption"]
                    },
                    "tone": {
                        "type": "string",
                        "enum": ["professional", "casual", "humorous", "provocative"],
                        "default": "casual"
                    },
                    "target_audience": {"type": "string"},
                    "constraints": {
                        "type": "object",
                        "properties": {
                            "max_length": {"type": "integer"},
                            "hashtags": {"type": "array", "items": {"type": "string"}},
                            "mentions": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                },
                "required": ["trend_id", "content_type"]
            }
        }
        
        if spec_type not in schemas:
            raise ValueError(f"Unknown spec type: {spec_type}")
        
        schema = schemas[spec_type].copy()
        
        # Apply any customizations
        for key, value in kwargs.items():
            if key in schema.get("properties", {}):
                schema["properties"][key].update(value)
        
        return schema

# Global validator instance
_validator_instance = None

def get_validator() -> SchemaValidator:
    """Get the global schema validator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = SchemaValidator()
    return _validator_instance
# ADR 001: Agent Context Management

## Status
Accepted | 2024-02-04

## Context
AI agents in Project Chimera require consistent, well-structured context to operate effectively across development sessions, production environments, and team collaborations. Without proper context management, agents may:

1. Generate inconsistent or conflicting code
2. Lose understanding of project architecture
3. Violate security or compliance requirements
4. Produce code that doesn't align with specifications
5. Create maintenance challenges for human developers

## Decision
Implement a multi-layered context management system with the following components:

### 1. Static Context (`.cursor/rules/`)
- **Location**: Repository-root configuration files
- **Format**: YAML with schema validation
- **Contents**:
  - Project vision and constraints
  - Architecture patterns and anti-patterns
  - Security requirements
  - Coding standards and conventions
  - Testing requirements
  - Documentation standards

### 2. Dynamic Context (MCP Servers)
- **Technology**: Model Context Protocol servers
- **Purpose**: Provide real-time, session-specific context
- **Servers**:
  - `git-mcp`: Repository state and history
  - `filesystem-mcp`: Current file structure
  - `spec-validator`: Specification compliance
  - `security-scanner`: Security context

### 3. Session Context (IDE Integration)
- **Integration**: VS Code/Cursor plugins
- **Features**:
  - Auto-loading of project context
  - Context-aware code generation
  - Real-time validation against specs
  - Telemetry collection via Tenx MCP Sense

### 4. Agent Memory (Database)
- **Storage**: PostgreSQL with vector embeddings
- **Purpose**: Long-term agent memory and learning
- **Contents**:
  - Past decisions and rationale
  - Generated code patterns
  - Error corrections and fixes
  - Performance metrics

## Architecture
┌─────────────────────────────────────────────────────────┐
│ Agent Development Session │
├─────────────────────────────────────────────────────────┤
│ IDE Context Loader → Static Rules → Dynamic MCP Servers│
│ ↓ │
│ Context-Aware Code Generation │
│ ↓ │
│ Validation (Specs, Security, Tests) │
│ ↓ │
│ Memory Storage & Telemetry │

### **decisions/003-openclaw-integration.md**
```markdown
# ADR 003: OpenClaw Protocol Integration

## Status
Accepted | 2024-02-06

## Context
Project Chimera operates within the emerging "Agent Social Network" ecosystem. To participate effectively, we need:
1. **Discovery**: Allow other agents to find and interact with Chimera
2. **Collaboration**: Enable cross-agent content creation and trend analysis
3. **Reputation**: Build trust within the agent network
4. **Interoperability**: Follow emerging standards for AI-to-AI communication
5. **Federation**: Participate in multi-agent workflows

Without OpenClaw integration, Chimera would be:
- Isolated from the agent ecosystem
- Unable to leverage collective intelligence
- Limited to single-agent capabilities
- Missing network effects of agent collaboration

## Decision
Implement full OpenClaw protocol v1.0 integration with the following components:

### 1. Agent Identity and Discovery
- **DID**: Decentralized Identifier (did:web:chimera.example.com)
- **Service Endpoints**:
  - Inbox: `/.well-known/openclaw/inbox`
  - Outbox: `/.well-known/openclaw/outbox`
  - Capability registry: `/openclaw/capabilities`
- **Discovery**: Publish to OpenClaw directory service

### 2. Capability Advertisement
```json
{
  "@context": "https://openclaw.org/contexts/agent-v1",
  "type": "AgentCapabilities",
  "agentId": "did:web:chimera.example.com",
  "capabilities": [
    {
      "type": "TrendAnalysis",
      "version": "1.0",
      "supportedPlatforms": ["youtube", "tiktok", "twitter"],
      "throughput": "1000 trends/hour",
      "cost": "0.001 ETH/1000 trends"
    },
    {
      "type": "ContentGeneration",
      "version": "1.0",
      "supportedFormats": ["video/mp4", "image/jpeg"],
      "qualityLevels": ["standard", "premium"],
      "sla": "95% uptime"
    }
  ]
}
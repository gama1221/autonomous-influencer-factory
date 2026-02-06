
### **decisions/002-database-partitioning.md**
```markdown
# ADR 002: Database Partitioning Strategy

## Status
Accepted | 2024-02-05

## Context
Project Chimera generates and processes large volumes of time-series data:
- Trends: 10,000+ daily from multiple platforms
- Content: 1,000+ daily generated assets
- Engagements: 100,000+ daily interactions
- Metrics: 1,000,000+ daily system metrics

Without partitioning, we face:
1. **Performance degradation** for recent data queries
2. **Maintenance challenges** with large tables
3. **Inefficient backups** of entire dataset
4. **Storage costs** for historical data
5. **Query complexity** for time-range queries

## Decision
Implement a hybrid partitioning strategy combining:

### 1. Time-Based Partitioning (Trends, Metrics)
- **Partition Key**: `discovered_at` (timestamp)
- **Granularity**: Daily partitions
- **Retention**: 90 days hot, 1 year warm, archive older
- **Naming**: `trends_y2024m02d04`

### 2. Platform-Based Partitioning (Engagements)
- **Partition Key**: `platform` (string)
- **Sub-partition**: Time-based (monthly)
- **Purpose**: Platform-specific query optimization
- **Naming**: `engagements_youtube_2024_02`

### 3. Status-Based Partitioning (Content)
- **Partition Key**: `status` (enum)
- **Sub-partition**: Time-based (weekly)
- **Purpose**: Efficient workflow management
- **Naming**: `content_published_2024_w05`

### 4. Hash-Based Partitioning (Users/Audience)
- **Partition Key**: `user_id` hash
- **Partitions**: 64 logical partitions
- **Purpose**: Even distribution for user data
- **Naming**: `audience_p00` to `audience_p63`

## Architecture
┌─────────────────────────────────────────────────────────┐
│ Partition Manager │
├─────────────────────────────────────────────────────────┤
│ Automatic Creation → Retention Enforcement → Archival │
│ ↓ │
│ Query Router (Partition Pruning) │
│ ↓ │
│ Read/Write to Appropriate Partition │
└─────────────────────────────────────────────────────────┘

## Implementation Details

### Partition Creation Strategy
```sql
-- Daily trend partition (auto-created)
CREATE TABLE trends_y2024m02d04 PARTITION OF trends
    FOR VALUES FROM ('2024-02-04 00:00:00') TO ('2024-02-05 00:00:00');

-- Platform engagement partition
CREATE TABLE engagements_youtube_2024_02 PARTITION OF engagements
    FOR VALUES WITH (MODULUS 4, REMAINDER 0)
    AND platform = 'youtube'
    AND created_at >= '2024-02-01' AND created_at < '2024-03-01';
```
# 🏛️ GLASS HOUSE STANDARD (Zero-Trust Protocol)

**Core Principle:** "No bead is closed until a Primary Key is produced."

### Execution Rules
1. **Native Only:** Agents use Python standard library (st, json, urllib). No pip installs inside tasks.
2. **File Proof:** Scan results saved to docs/*.json before DB insert.
3. **Zilliz Truth:** Final step MUST insert into 
exus_events and return the primary_key.
4. **Verify Count:** Mayor verifies entity count increased by exactly N.

### Schema Requirement
- **Collection:** 
exus_events
- **Vector Dim:** 768 (FLOAT_VECTOR)
- **Primary Key:** primary_key (auto-generated INT64)

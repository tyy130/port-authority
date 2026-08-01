---
name: port-request
description: Request an available port from Port Authority before building
user-invocable: true
allowed-tools: Bash
---

# Request Port from Port Authority

Request an available port allocation from Port Authority instead of hardcoding or scanning for ports.

**Usage:**

```bash
/port-request myproject myservice [pool]
```

**Examples:**

```bash
# Get a web service port
/port-request debtlogic admin

# Get a specific pool
/port-request buzz relay --pool web

# Check all allocations
/port-request status
```

**What it does:**

1. Queries the Port Authority daemon
2. Allocates an available port for your project/service
3. Tracks the allocation centrally
4. Prevents conflicts across all your projects

**Integration:**
When building, use this skill instead of hardcoding ports. The allocated port will be used throughout your build.

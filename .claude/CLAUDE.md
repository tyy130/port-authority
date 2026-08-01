# Port Authority Integration

When building or starting services, **always request ports from Port Authority** instead of hardcoding them.

## Before (old way):

```bash
# ❌ Don't do this
app.run(port=3000)
docker run -p 8000:8000 myservice
```

## After (Port Authority way):

```bash
# ✅ Do this instead
PORT=$(port myproject myservice)
app.run(port=$PORT)
docker run -p $PORT:$PORT myservice
```

## Integration Pattern

When you start building something:

1. **Request a port first:**

   ```bash
   PORT=$(port myproject myservice)
   ```

2. **Use that port throughout:**

   ```bash
   # In scripts, Docker, config files, etc.
   docker run -p $PORT:$PORT app
   PORT=$PORT npm start
   ```

3. **The allocation is tracked centrally:**
   ```bash
   port status  # See all allocations
   ```

## Why this matters

- **No conflicts**: Port Authority prevents two services using the same port
- **Reproducible**: Each service gets a consistent port
- **Observable**: `port status` shows what's running where
- **Cross-project**: Works across all your projects (Buzz, DebtLogic, etc.)

## Examples

### Web service

```bash
PORT=$(port myproject web)
python app.py --port $PORT
```

### Database

```bash
PORT=$(port myproject postgres)
docker run -p $PORT:5432 postgres
```

Recognized service names (postgres, redis, mysql, mongodb, and others) get their standard port automatically when it's free, so `$PORT` is usually `5432` here — falling back to a pool port only if something else already has it. Either way this pattern is correct without changes: `docker run -p $PORT:5432` maps whatever host port got allocated to the container's real internal port.

### API server

```bash
PORT=$(port myproject api)
npm start -- --port $PORT
```

## Agents: Use this pattern by default

When building anything with a port, the mental model should be:

> "What port should this use? Let me check with Port Authority..."

Not:

> "Port 3000 should work..."

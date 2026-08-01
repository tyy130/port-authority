# Port Authority Integration Guide

How to integrate Port Authority into your projects so agents naturally use it.

## 1. Install Port Authority (once, globally)

```bash
cd ~/.local/src/port-authority
./install.sh
```

This sets up the daemon and CLI tools system-wide.

## 2. Add to Your Project

### Option A: Git Submodule (Recommended)

```bash
cd ~/Dev/myproject
git submodule add https://github.com/tyy130/port-authority.git .port-authority
```

### Option B: Copy Files

```bash
cp -r ~/.local/src/port-authority/.claude .claude/port-authority
```

## 3. Update Project CLAUDE.md

Add to your project's `.claude/CLAUDE.md` or `.claude/CLAUDE-port-authority.md`:

```markdown
@.port-authority/.claude/CLAUDE.md
```

This makes Port Authority instructions available to all agents in the project.

## 4. Add Claude Code Skill (Optional but Recommended)

Create `.claude/skills/port-request/SKILL.md` in your project:

```bash
cp ~/.local/src/port-authority/.claude/skills/port-request/SKILL.md .claude/skills/
```

Now agents can do:

```bash
/port-request myproject myservice
```

## 5. Set Up Git Hook (Optional)

Copy pre-commit hook to catch hardcoded ports:

```bash
cp ~/.local/src/port-authority/hooks/pre-commit .git/hooks/
chmod +x .git/hooks/pre-commit
```

Now git will warn when committing hardcoded ports:

```
⚠️  Port Authority: Hardcoded ports detected
  ➜ app.run(port=3000)

💡 Suggestion: Use Port Authority instead:
  PORT=$(port myproject myservice)
```

## 6. Usage in Your Project

### Start a service:

```bash
# Request port
PORT=$(port myproject backend)

# Use it
npm start -- --port $PORT
```

### Docker services:

```bash
# In your docker-compose or script:
PORT=$(port myproject database)
docker run -p $PORT:5432 postgres
```

### Agent instructions:

When an agent builds something in your project, it will see the Port Authority CLAUDE.md and naturally think:

> "I need to start a service... let me request a port from Port Authority first"

## 7. Multiple Services in One Project

```bash
# Each gets its own allocated port
WEB_PORT=$(port myproject web)
API_PORT=$(port myproject api)
DB_PORT=$(port myproject database)

# Use them:
docker-compose -e WEB_PORT=$WEB_PORT -e API_PORT=$API_PORT -e DB_PORT=$DB_PORT up
```

## 8. Check Status

```bash
port status                 # All allocations
port status myproject       # Your project only
```

## Example: Integrating into Buzz

```bash
cd ~/.local/src/buzz

# Add Port Authority integration
cp ~/.local/src/port-authority/.claude/CLAUDE.md .claude/CLAUDE-ports.md

# Or add to existing .claude/CLAUDE.md:
echo "@~/.local/src/port-authority/.claude/CLAUDE.md" >> .claude/CLAUDE.md

# Now when building, agents will know to use Port Authority
```

## Integration Checklist

- [ ] Port Authority daemon installed globally
- [ ] Project has `.claude/CLAUDE.md` (or CLAUDE-port-authority.md)
- [ ] (Optional) Claude Code skill copied to `.claude/skills/`
- [ ] (Optional) Git hook installed to `.git/hooks/pre-commit`
- [ ] Tested: `port myproject testservice` returns a port
- [ ] Updated startup scripts to use `$(port ...)`

## Troubleshooting

**"Port Authority daemon not running"**

```bash
systemctl --user status port-authority.service
systemctl --user start port-authority.service
```

**"Permission denied" on hooks**

```bash
chmod +x .git/hooks/pre-commit
```

**Want to bypass the pre-commit warning**

```bash
git commit --no-verify
```

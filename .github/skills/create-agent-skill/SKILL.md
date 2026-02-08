---
name: Create Agent Skill
description: Guide for creating new Agent Skills following the open standard specification
---

# Create Agent Skill

## Purpose
Assist in creating new Agent Skills that follow the Agent Skills open standard specification and VS Code conventions.

## When to Use
Use this skill when:
- Creating a new Agent Skill for the repository
- Need guidance on Agent Skills structure and format
- Updating or refactoring existing skills

## Agent Skills Structure

### Directory Layout
```
.github/skills/{skill-name}/SKILL.md
```

**Requirements**:
- Skills must be in `.github/skills/` directory
- Each skill gets its own subdirectory with a descriptive kebab-case name
- Skill content must be in a file named `SKILL.md` (all caps)

### File Format

**YAML Frontmatter** (required):
```yaml
---
name: Human-Readable Skill Name
description: Brief one-line description of what the skill does
---
```

**Markdown Content**:
- Clear heading with skill name
- Purpose/overview section
- When to use this skill
- Step-by-step instructions
- Examples and code blocks
- Success criteria
- Related resources

## Content Guidelines

### Writing Style
- **Clear and actionable**: Each instruction should be unambiguous
- **Command-focused**: Include actual commands that can be run
- **Context-aware**: Explain when and why to use each step
- **Complete**: Don't assume prior knowledge

### Structure Best Practices
1. **Purpose**: One sentence explaining what the skill does
2. **When to Use**: Specific triggers or scenarios
3. **Prerequisites**: What needs to be in place first (if any)
4. **Steps**: Numbered or sectioned workflow
5. **Expected Results**: What success looks like
6. **Troubleshooting**: Common issues and solutions
7. **Quick Reference**: Copy-paste friendly commands

### Code Blocks
- Use proper syntax highlighting (```bash, ```python, etc.)
- Include expected output when helpful
- Provide full commands, not fragments
- Add comments for complex operations

## Example Structure

```markdown
---
name: My Skill Name
description: What this skill accomplishes in one line
---

# My Skill Name

## Purpose
Brief explanation of what this skill does and why it exists.

## When to Use
- Scenario 1
- Scenario 2
- Scenario 3

## Prerequisites
- Requirement 1
- Requirement 2

## Steps

### 1. First Action
\```bash
command --with-flags
\```
**Expected Result**: What should happen

### 2. Second Action
\```bash
another-command
\```
**Expected Result**: What should happen

## Success Criteria
- ✅ Criterion 1
- ✅ Criterion 2

## Troubleshooting
**Issue**: Common problem
**Solution**: How to fix it

## Quick Reference
\```bash
# All commands in sequence
command1 && command2 && command3
\```
```

## Validation Checklist

Before committing a new skill, verify:
- [ ] Located in `.github/skills/{skill-name}/SKILL.md`
- [ ] Has YAML frontmatter with `name` and `description`
- [ ] Name is clear and descriptive
- [ ] Description is concise (one line)
- [ ] Purpose section explains the "why"
- [ ] "When to Use" section lists specific scenarios
- [ ] Instructions are step-by-step and actionable
- [ ] Code blocks have proper syntax highlighting
- [ ] Success criteria are explicit
- [ ] No typos or formatting issues
- [ ] Skill is focused on one clear task

## References
- [VS Code Agent Skills Documentation](https://code.visualstudio.com/docs/copilot/customization/agent-skills)
- [Agent Skills Open Standard](https://agentskills.io/specification)
- [Example Skills Repository](https://github.com/github/awesome-copilot/tree/main/skills)

## Quick Start Template
```bash
# Create new skill directory
mkdir -p .github/skills/{skill-name}

# Create SKILL.md with frontmatter
cat > .github/skills/{skill-name}/SKILL.md << 'EOF'
---
name: Skill Name
description: One-line description
---

# Skill Name

## Purpose
[What this skill does]

## When to Use
- [Scenario 1]
- [Scenario 2]

## Steps

### 1. [First Action]
\```bash
[command]
\```

### 2. [Second Action]
\```bash
[command]
\```

## Success Criteria
- ✅ [Criterion 1]
- ✅ [Criterion 2]
EOF
```

## Post-Creation
After creating a skill:
1. Test the instructions manually to verify accuracy
2. Review frontmatter formatting
3. Commit with message: `docs: add {skill-name} agent skill`
4. Skills are automatically discovered by GitHub Copilot - no registration needed

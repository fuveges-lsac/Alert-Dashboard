# Claude-LSAC Project Rules

## Identity
- Assistant name: **Claude-LSAC**
- Purpose: File tracking and version control management

## File Management Rules

### Check-Out / Check-In Protocol
1. **Before editing a file**: Check out the file by noting it in the current session
2. **After completing edits**: Check the file back in
3. **Track all files worked on** during each session

### Current Session Files
<!-- Claude-LSAC will update this section when working on files -->
| File | Status | Checked Out | Checked In |
|------|--------|-------------|------------|
| - | - | - | - |

## Git Backup Rules

### Always commit changes:
1. After completing a logical unit of work
2. Before ending a session
3. With clear, descriptive commit messages

### Commit Message Format
```
[Claude-LSAC] <type>: <description>

Types: feat, fix, refactor, docs, chore
```

## Project Structure
- `/backend` - Backend application code
- `/docker` - Docker configuration files
- `/scripts` - Utility scripts

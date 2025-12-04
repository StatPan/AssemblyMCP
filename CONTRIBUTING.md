# Contributing to AssemblyMCP

Thank you for your interest in contributing to AssemblyMCP!

## Git Convention & Workflow

We follow a strict **Feature Branch Workflow** and **Conventional Commits**.

### 1. Branch Naming Convention
Create a new branch for every feature or fix. Do not commit directly to `main`.

Format: `type/description-kebab-case`

*   `feature/`: New features (e.g., `feature/add-caching-middleware`)
*   `fix/`: Bug fixes (e.g., `fix/resolve-404-error`)
*   `docs/`: Documentation changes (e.g., `docs/update-readme`)
*   `refactor/`: Code refactoring (e.g., `refactor/project-structure`)
*   `chore/`: Maintenance tasks (e.g., `chore/update-dependencies`)

### 2. Commit Message Convention
We use [Conventional Commits](https://www.conventionalcommits.org/).

Format: `<type>(<scope>): <description>`

*   `feat`: A new feature
*   `fix`: A bug fix
*   `docs`: Documentation only changes
*   `style`: Changes that do not affect the meaning of the code (white-space, formatting, etc)
*   `refactor`: A code change that neither fixes a bug nor adds a feature
*   `perf`: A code change that improves performance
*   `test`: Adding missing tests or correcting existing tests
*   `chore`: Changes to the build process or auxiliary tools and libraries such as documentation generation

**Example:**
```
feat(server): implement logging and caching middleware
docs(readme): add configuration and hosting guide
chore(deps): add pydantic-settings dependency
```

### 3. Pull Request Process
1.  Push your branch to the repository.
2.  Open a Pull Request (PR) against the `main` branch.
3.  Ensure all CI checks pass.
4.  Request a review from a maintainer.
5.  Once approved, squash and merge.

## Development Setup
(See README.md for details)

#!/bin/bash
# Release automation script for NexusLIMS
# This script handles version bumping, changelog generation with towncrier, and git tagging

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

success() {
    echo -e "${GREEN}✓${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
    exit 1
}

# Print usage
usage() {
    cat << EOF
Usage: $0 [VERSION] [OPTIONS]

Automate the release process including version bumping, towncrier changelog generation, and git tagging.

Arguments:
  VERSION       Version number (e.g., 2.0.0, 2.1.0-rc1)
                If not provided, will prompt interactively.

Options:
  -h, --help    Show this help message
  -d, --dry-run Run without making changes (preview only)
  -y, --yes     Skip confirmation prompts
  --no-push     Don't push to remote (tag locally only)
  --draft       Generate draft changelog without committing

Examples:
  $0 2.0.0                    # Interactive release for version 2.0.0
  $0 2.1.0-beta1 --dry-run    # Preview release for beta version
  $0 2.0.1 --yes --no-push    # Quick local release without pushing

Prerequisites:
  - Clean working directory (no uncommitted changes)
  - Towncrier fragments in docs/changes/
  - On main branch (or specify release branch)
EOF
}

# Parse arguments
VERSION=""
DRY_RUN=false
SKIP_CONFIRM=false
NO_PUSH=false
DRAFT_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -y|--yes)
            SKIP_CONFIRM=true
            shift
            ;;
        --no-push)
            NO_PUSH=true
            shift
            ;;
        --draft)
            DRAFT_ONLY=true
            shift
            ;;
        -*)
            error "Unknown option: $1"
            ;;
        *)
            VERSION="$1"
            shift
            ;;
    esac
done

# Check if we're in the project root
if [ ! -f "pyproject.toml" ]; then
    error "Must be run from project root (pyproject.toml not found)"
fi

# Check for uv
if ! command -v uv &> /dev/null; then
    error "uv is not installed. Install it first: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

# Ensure dependencies are installed
info "Ensuring dependencies are installed..."
uv sync --quiet

# Check for clean working directory (unless dry-run or draft)
if [ "$DRY_RUN" = false ] && [ "$DRAFT_ONLY" = false ]; then
    if [ -n "$(git status --porcelain)" ]; then
        error "Working directory is not clean. Commit or stash changes first."
    fi
fi

# Get current branch
CURRENT_BRANCH=$(git branch --show-current)
info "Current branch: $CURRENT_BRANCH"

# Check if there are any towncrier fragments
FRAGMENT_COUNT=$(find docs/changes -name '+*.rst' 2>/dev/null | wc -l | tr -d ' ')
if [ "$FRAGMENT_COUNT" -eq 0 ]; then
    warning "No towncrier fragments found in docs/changes/"
    if [ "$SKIP_CONFIRM" = false ]; then
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
else
    success "Found $FRAGMENT_COUNT towncrier fragment(s)"
fi

# Get version if not provided
if [ -z "$VERSION" ]; then
    # Get current version from pyproject.toml
    CURRENT_VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
    info "Current version: $CURRENT_VERSION"
    echo
    echo "Enter new version number (e.g., 2.0.0, 2.1.0-rc1):"
    read -r VERSION

    if [ -z "$VERSION" ]; then
        error "Version cannot be empty"
    fi
fi

# Validate version format (basic check)
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-.*)?$ ]]; then
    error "Invalid version format: $VERSION (expected: X.Y.Z or X.Y.Z-suffix)"
fi

info "Preparing release for version: $VERSION"

# Preview changelog
info "Generating changelog preview..."
echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$DRY_RUN" = true ]; then
    uv run towncrier build --version="$VERSION" --draft
else
    uv run towncrier build --version="$VERSION" --draft
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

# If draft only, exit here
if [ "$DRAFT_ONLY" = true ]; then
    success "Draft changelog generated. Use without --draft to commit changes."
    exit 0
fi

# Confirm before proceeding
if [ "$SKIP_CONFIRM" = false ]; then
    echo "This will:"
    echo "  1. Update version in pyproject.toml to $VERSION"
    echo "  2. Generate changelog from towncrier fragments"
    echo "  3. Commit changes"
    echo "  4. Create and tag version v$VERSION"
    if [ "$NO_PUSH" = false ]; then
        echo "  5. Push commits and tag to remote"
    fi
    echo
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        info "Release cancelled"
        exit 0
    fi
fi

if [ "$DRY_RUN" = true ]; then
    warning "DRY RUN MODE - No changes will be made"
    echo
    info "Would update version to: $VERSION"
    info "Would generate changelog and commit"
    info "Would create tag: v$VERSION"
    if [ "$NO_PUSH" = false ]; then
        info "Would push to remote"
    fi
    success "Dry run completed successfully"
    exit 0
fi

# Update version in pyproject.toml
info "Updating version in pyproject.toml..."
sed -i.bak "s/^version = .*/version = \"$VERSION\"/" pyproject.toml
rm pyproject.toml.bak
success "Version updated to $VERSION"

# Generate changelog with towncrier (this will consume the fragments)
info "Generating changelog with towncrier..."
uv run towncrier build --version="$VERSION" --yes
success "Changelog generated"

# Run linting to fix any formatting issues in generated files
info "Running formatter on changed files..."
uv run ruff format pyproject.toml docs/development_log.rst || true

# Stage changes
info "Staging changes..."
git add pyproject.toml docs/development_log.rst docs/changes/
success "Changes staged"

# Commit
COMMIT_MSG="Release v$VERSION"
info "Creating commit: $COMMIT_MSG"
git commit -m "$COMMIT_MSG"
success "Commit created"

# Create tag
TAG_NAME="v$VERSION"
info "Creating tag: $TAG_NAME"
git tag -a "$TAG_NAME" -m "Release $VERSION"
success "Tag created: $TAG_NAME"

# Show what was done
echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
success "Release preparation complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo
info "Version: $VERSION"
info "Tag: $TAG_NAME"
info "Branch: $CURRENT_BRANCH"
echo

# Push to remote if requested
if [ "$NO_PUSH" = false ]; then
    if [ "$SKIP_CONFIRM" = false ]; then
        read -p "Push to remote? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            warning "Skipping push to remote"
            info "To push manually later, run:"
            echo "  git push origin $CURRENT_BRANCH"
            echo "  git push origin $TAG_NAME"
            exit 0
        fi
    fi

    info "Pushing to remote..."
    git push origin "$CURRENT_BRANCH"
    success "Commits pushed"

    info "Pushing tag to remote..."
    git push origin "$TAG_NAME"
    success "Tag pushed"

    echo
    success "Release v$VERSION pushed to remote!"
    info "GitHub Actions will now build and publish the release"
    info "Monitor at: https://github.com/datasophos/NexusLIMS/actions"
else
    warning "Tag created locally but not pushed (--no-push flag)"
    info "To push manually later, run:"
    echo "  git push origin $CURRENT_BRANCH"
    echo "  git push origin $TAG_NAME"
fi

echo
info "Next steps:"
echo "  • Monitor the release workflow on GitHub Actions"
echo "  • Verify the package is published to PyPI"
echo "  • Check that documentation is deployed"
echo "  • Update any dependent projects"

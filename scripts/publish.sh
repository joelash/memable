#!/bin/bash
set -e

cd "$(dirname "$0")/.."

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

usage() {
    echo "Usage: $0 [patch|minor|major|<version>]"
    echo ""
    echo "Examples:"
    echo "  $0 patch     # 0.1.2 -> 0.1.3"
    echo "  $0 minor     # 0.1.2 -> 0.2.0"
    echo "  $0 major     # 0.1.2 -> 1.0.0"
    echo "  $0 0.2.0     # explicit version"
    echo "  $0           # publish current version (no bump)"
    exit 1
}

echo -e "${BLUE}🐘 memable publish script${NC}"
echo ""

# Get current versions
PY_VERSION=$(grep '^version = ' pyproject.toml | cut -d'"' -f2)
NPM_VERSION=$(grep '"version"' packages/memable/package.json | head -1 | cut -d'"' -f4)

echo "Current Python version: $PY_VERSION"
echo "Current npm version:    $NPM_VERSION"

if [ "$PY_VERSION" != "$NPM_VERSION" ]; then
    echo -e "${RED}⚠️  Version mismatch! Syncing to Python version...${NC}"
    # Use sed to update npm version to match Python
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/\"version\": \"$NPM_VERSION\"/\"version\": \"$PY_VERSION\"/" packages/memable/package.json
    else
        sed -i "s/\"version\": \"$NPM_VERSION\"/\"version\": \"$PY_VERSION\"/" packages/memable/package.json
    fi
    NPM_VERSION=$PY_VERSION
    echo "Synced npm to $PY_VERSION"
fi

# Handle version bump argument
if [ -n "$1" ]; then
    CURRENT=$PY_VERSION
    IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"
    
    case "$1" in
        patch)
            NEW_VERSION="$MAJOR.$MINOR.$((PATCH + 1))"
            ;;
        minor)
            NEW_VERSION="$MAJOR.$((MINOR + 1)).0"
            ;;
        major)
            NEW_VERSION="$((MAJOR + 1)).0.0"
            ;;
        -h|--help)
            usage
            ;;
        *)
            # Assume explicit version
            if [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
                NEW_VERSION="$1"
            else
                echo -e "${RED}Invalid version: $1${NC}"
                usage
            fi
            ;;
    esac
    
    echo ""
    echo -e "${YELLOW}Bumping version: $CURRENT -> $NEW_VERSION${NC}"
    
    # Update Python version
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/version = \"$CURRENT\"/version = \"$NEW_VERSION\"/" pyproject.toml
        sed -i '' "s/\"version\": \"$CURRENT\"/\"version\": \"$NEW_VERSION\"/" packages/memable/package.json
    else
        sed -i "s/version = \"$CURRENT\"/version = \"$NEW_VERSION\"/" pyproject.toml
        sed -i "s/\"version\": \"$CURRENT\"/\"version\": \"$NEW_VERSION\"/" packages/memable/package.json
    fi
    
    PY_VERSION=$NEW_VERSION
    NPM_VERSION=$NEW_VERSION
    
    # Commit version bump
    git add pyproject.toml packages/memable/package.json
    git commit -m "chore: Bump version to $NEW_VERSION"
    echo -e "${GREEN}Committed version bump${NC}"
fi

echo ""
echo -e "${BLUE}Publishing version $PY_VERSION${NC}"
echo ""

# Build and publish Python
echo -e "${GREEN}Building Python package...${NC}"
rm -rf dist/
python3 -m build

echo ""
echo -e "${GREEN}Publishing to PyPI...${NC}"
echo -e "${YELLOW}(You may be prompted for PyPI credentials)${NC}"
twine upload --skip-existing dist/*

echo ""
# Build and publish npm
echo -e "${GREEN}Building npm package...${NC}"
cd packages/memable
npm ci
npm run build

echo ""
# Check npm login status
if ! npm whoami &>/dev/null; then
    echo -e "${YELLOW}Not logged in to npm. Running npm login...${NC}"
    npm login
fi

echo -e "${GREEN}Publishing to npm...${NC}"
echo -e "${YELLOW}(You may be prompted for OTP)${NC}"
npm publish --access public

cd ../..

# Tag and push
echo ""
echo -e "${GREEN}Creating git tag v$PY_VERSION...${NC}"
git tag -a "v$PY_VERSION" -m "Release v$PY_VERSION"
git push origin main --tags

echo ""
echo -e "${GREEN}✅ Published memable v$PY_VERSION to PyPI and npm!${NC}"

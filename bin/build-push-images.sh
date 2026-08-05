#!/usr/bin/env bash
# Build a component's Docker image(s) from a git branch and push them to
# Docker Hub tagged with the branch name, to test a PR branch on preprod
# before it is merged. The tag drops the branch's type prefix and replaces
# characters invalid in a docker tag with '-' (e.g. feat/my-fix -> my-fix).
#
# Usage: bin/build-push-images.sh <api|engine|platform> <branch>
#
# Requires docker (with buildx) and a Docker Hub login with push rights on
# the pyronear organization. Builds target a fixed platform per image; when
# that differs from the host architecture, cross-building needs QEMU/binfmt
# (Docker Desktop ships it; on bare Linux install qemu-user-static).
set -euo pipefail

usage() {
    echo "Usage: $0 <api|engine|platform> <branch>" >&2
    echo "  api       pyronear/pyro-api          -> pyronear/alert-api:<branch> (linux/amd64)" >&2
    echo "  engine    pyronear/pyro-engine       -> pyronear/pyro-engine:<branch> + pyronear/pyro-camera-api:<branch> (linux/arm64)" >&2
    echo "  platform  pyronear/new-pyro-platform -> pyronear/pyro-platform-react:<branch> (linux/amd64)" >&2
    exit 1
}

[ $# -eq 2 ] || usage
COMPONENT=$1
BRANCH=$2

# Tag = branch name without its type prefix (feat/my-fix -> my-fix); only
# the first path component is dropped so nested branches keep distinct tags
# (feat/team/foo -> team-foo). Sanitized to docker tag rules: [a-zA-Z0-9_]
# first, then [a-zA-Z0-9._-], max 128 chars.
TAG=$(printf '%s' "${BRANCH#*/}" | tr -c 'a-zA-Z0-9_.-' '-' | sed 's/^[.-]*//' | cut -c1-128)
[ -n "$TAG" ] || { echo "ERROR: branch name '$BRANCH' yields an empty docker tag" >&2; exit 1; }

docker buildx version >/dev/null 2>&1 || { echo "ERROR: docker buildx is not available" >&2; exit 1; }

case "$COMPONENT" in
    api)      GITHUB_REPO=pyro-api ;;
    engine)   GITHUB_REPO=pyro-engine ;;
    platform) GITHUB_REPO=new-pyro-platform ;;
    *) usage ;;
esac

SRC_DIR=$(mktemp -d)
trap 'rm -rf "$SRC_DIR"' EXIT

echo "==> Cloning pyronear/${GITHUB_REPO}@${BRANCH}"
git clone --depth 1 --branch "$BRANCH" "https://github.com/pyronear/${GITHUB_REPO}.git" "$SRC_DIR"
cd "$SRC_DIR"

echo "==> Building ${COMPONENT}@${BRANCH}, pushing with tag :${TAG}"

case "$COMPONENT" in
    api)
        docker buildx build --platform linux/amd64 -f src/Dockerfile \
            -t "pyronear/alert-api:${TAG}" --push .
        ;;
    engine)
        # Same images/contexts as .github/workflows/build-push-image.yml in
        # pyro-engine; arm64 only because they run on the Raspberry Pis.
        docker buildx build --platform linux/arm64 -f Dockerfile \
            -t "pyronear/pyro-engine:${TAG}" --push .
        docker buildx build --platform linux/arm64 -f pyro_camera_api/Dockerfile \
            -t "pyronear/pyro-camera-api:${TAG}" --push pyro_camera_api
        ;;
    platform)
        # CI builds the app outside docker; the Dockerfile only copies dist/
        # into nginx. No packageManager field in package.json, so run pnpm
        # via npx instead of corepack; pnpm 9 matches lockfileVersion 9.0
        # and, unlike pnpm 10, runs the esbuild postinstall script vite
        # needs. Run as the host user so node_modules/dist are not
        # root-owned (the cleanup trap must be able to delete them on
        # Linux hosts).
        docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
            -v "$SRC_DIR":/app -w /app node:24 \
            sh -c "npx -y pnpm@9 install --frozen-lockfile && npx -y pnpm@9 build"
        docker buildx build --platform linux/amd64 \
            -t "pyronear/pyro-platform-react:${TAG}" --push .
        ;;
esac

echo "==> Done: ${COMPONENT}@${BRANCH} pushed as :${TAG}"

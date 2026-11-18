#!/usr/bin/env bash
# Build a component's Docker image(s) from a git branch and push them to
# Docker Hub tagged with the branch name, to test a PR branch on preprod
# before it is merged. The tag drops the branch's type prefix and replaces
# characters invalid in a docker tag with '-' (e.g. feat/my-fix -> my-fix).
#
# Usage: [PLATFORMS=<platform>[,<platform>]] bin/build-push-images.sh <api|engine|platform> <branch>
#
# PLATFORMS overrides the target platform(s), e.g. PLATFORMS=linux/arm64 for a
# faster engine build when only Raspberry Pis need it.
#
# Requires docker (with buildx) and a Docker Hub login with push rights on
# the pyronear organization. Each image has a default platform; when the target
# differs from the host architecture, cross-building needs QEMU/binfmt
# (Docker Desktop ships it; on bare Linux install qemu-user-static).
# Building several platforms at once (the engine default) is not supported by
# the classic "docker" builder driver without the containerd image store: run
# `docker buildx create --use` once, or turn on the containerd image store.
set -euo pipefail

usage() {
    echo "Usage: [PLATFORMS=<platform>[,<platform>]] $0 <api|engine|platform> <branch>" >&2
    echo "  api       pyronear/pyro-api          -> pyronear/alert-api:<branch> (linux/amd64)" >&2
    echo "  engine    pyronear/pyro-engine       -> pyronear/pyro-engine:<branch> + pyronear/pyro-camera-api:<branch> (linux/amd64,linux/arm64)" >&2
    echo "  platform  pyronear/new-pyro-platform -> pyronear/pyro-platform-react:<branch> (linux/amd64)" >&2
    echo "  PLATFORMS overrides the platform(s) above, e.g. PLATFORMS=linux/arm64" >&2
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

# Refuse tags used for releases so a test branch can never overwrite them.
if [[ "$TAG" =~ ^(latest|main|master|develop|stable|v?[0-9]+(\.[0-9]+)*)$ ]]; then
    echo "ERROR: tag '$TAG' is reserved (latest or a version number); rename the branch" >&2
    exit 1
fi

docker buildx version >/dev/null 2>&1 || { echo "ERROR: docker buildx is not available" >&2; exit 1; }

case "$COMPONENT" in
    api)      GITHUB_REPO=pyro-api;          DEFAULT_PLATFORMS=linux/amd64 ;;
    # Both by default, like the pyro-engine CI: engines run on Raspberry Pis (arm64)
    # and on x86 servers; docker pulls the image matching the host from one tag.
    engine)   GITHUB_REPO=pyro-engine;       DEFAULT_PLATFORMS=linux/amd64,linux/arm64 ;;
    platform) GITHUB_REPO=new-pyro-platform; DEFAULT_PLATFORMS=linux/amd64 ;;
    *) usage ;;
esac
PLATFORMS=${PLATFORMS:-$DEFAULT_PLATFORMS}
[[ "$PLATFORMS" =~ ^linux/[a-z0-9]+(/v[0-9])?(,linux/[a-z0-9]+(/v[0-9])?)*$ ]] \
    || { echo "ERROR: invalid PLATFORMS '$PLATFORMS' (expected e.g. linux/amd64,linux/arm64)" >&2; exit 1; }

SRC_DIR=$(mktemp -d)
trap 'rm -rf "$SRC_DIR"' EXIT

echo "==> Cloning pyronear/${GITHUB_REPO}@${BRANCH}"
git clone --depth 1 --branch "$BRANCH" "https://github.com/pyronear/${GITHUB_REPO}.git" "$SRC_DIR"
cd "$SRC_DIR"

echo "==> Building ${COMPONENT}@${BRANCH} for ${PLATFORMS}, pushing with tag :${TAG}"

case "$COMPONENT" in
    api)
        docker buildx build --platform "$PLATFORMS" -f src/Dockerfile \
            -t "pyronear/alert-api:${TAG}" --push .
        ;;
    engine)
        # Same images/contexts as .github/workflows/build-push-image.yml in
        # pyro-engine.
        docker buildx build --platform "$PLATFORMS" -f Dockerfile \
            -t "pyronear/pyro-engine:${TAG}" --push .
        docker buildx build --platform "$PLATFORMS" -f pyro_camera_api/Dockerfile \
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
        docker run --rm --pull=always --user "$(id -u):$(id -g)" -e HOME=/tmp \
            -v "$SRC_DIR":/app -w /app node:24.22.1 \
            sh -c "npx -y pnpm@9 install --frozen-lockfile && npx -y pnpm@9 build"
        docker buildx build --platform "$PLATFORMS" \
            -t "pyronear/pyro-platform-react:${TAG}" --push .
        ;;
esac

echo "==> Done: ${COMPONENT}@${BRANCH} pushed as :${TAG} (${PLATFORMS})"

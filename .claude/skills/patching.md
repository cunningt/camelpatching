# Camelpatching Skill

Create downstream product branches for Red Hat Camel from upstream Apache release tags.

## Overview

This tool automates the creation of product branches in `jboss-fuse/*` repos. It handles three repositories:

| Script | Repo | Branch Pattern |
|--------|------|----------------|
| `camel.py` | `jboss-fuse/camel` | `camel-{V}-branch` |
| `csb.py` | `jboss-fuse/camel-spring-boot` | `camel-spring-boot-{V}-branch` |
| `kamelet.py` | `jboss-fuse/camel-kamelets` | `camel-kamelets-{V}-branch` |

## Repos NOT Covered

spring-boot-undertow, camel-spring-boot-examples, camel-launcher, camel-upgrade-recipes, sap-quickstarts, fuse-components, narayana-spring-boot, jbang-catalog. These must be branched manually or via a separate process.

## Branch Layout

- **`main`** -- Old Perl scripts targeting 4.10.x (legacy)
- **Version branches** (e.g., `origin/camel-4.19.0-branch`) -- Active Python scripts with rich CLI output, debug mode, 3-way merge conflict handling

Always start from the **latest version branch** when creating a new version.

## Workflow for a New Version

### 1. Prepare the scripts

Checkout the latest version branch (e.g., `git checkout origin/camel-4.19.0-branch -b camel-4.21.0-branch`), then update:

- **`camel.py`**: Set `vers = "4.21.0"` and `currentprodbranch = "camel-4.19.0-branch"` (or whatever the last produced branch was)
- **`csb.py`**: Set `vers = "4.21.0"` and `currentprodbranch = "camel-spring-boot-4.19.0-branch"`
- **`kamelet.py`**: Set `vers = "4.21.0"` and `currentprodbranch = "camel-kamelets-4.19.0-branch"`
- **`csb-rewrite.yml`**: Update all version properties:
  - `camel-community-version` (previous camel version for community deps)
  - `camel-spring-boot-community.version`
  - `camel-kamelets-version`
  - `camel-sap.version`, `camel-cics.version`, `narayana-spring-boot.version`
  - All other pinned dependency versions as needed

### 2. Review and update patches

Patches in `camelpatches/`, `csbpatches/`, `kameletpatches/` may need rebasing for the new upstream version. Check each patch applies cleanly.

### 3. Execute in order

```bash
# Install Python dependency
pip install rich

# 1. Camel FIRST (CSB depends on it)
python3 camel.py

# 2. Camel Spring Boot
python3 csb.py

# 3. Camel Kamelets (independent)
python3 kamelet.py
```

### 4. Debug options

All Python scripts support:
- `python3 camel.py endbeforepre` -- Stop before pre-patches
- `python3 camel.py endbeforeplugin` -- Stop before prod-maven-plugin (camel only)
- `python3 camel.py endbeforepost` -- Stop before post-patches
- `python3 camel.py --debug` -- Step through patches one by one
- `python3 camel.py --use-reject` -- Use `.rej` files instead of 3-way merge for conflicts

### 5. Push branches

Branches are created locally. After verification, push manually:
```bash
cd camel-4.21.0-branch && git push origin camel-4.21.0-branch
cd camel-spring-boot-4.21.0-branch && git push origin camel-spring-boot-4.21.0-branch
cd camel-kamelets-4.21.0-branch && git push origin camel-kamelets-4.21.0-branch
```

## Environment Requirements

- Java 21 (camel, csb) / Java 17 (kamelets)
- Maven 3.9.9 at `/usr/local/apache-maven-3.9.9/bin/mvn`
- SSH access to `github.com:jboss-fuse/*.git` and `github.com:apache/*.git`
- `gsed` (GNU sed, macOS: `brew install gnu-sed`)
- Python 3.6+ with `rich` library

## Pipeline Steps (per script)

1. Clone jboss-fuse fork + previous product branch
2. Add apache upstream remote, fetch tags
3. Checkout upstream tag into new product branch
4. `mvn versions:set` to `{V}-SNAPSHOT`
5. Apply pre-patches (`pre-*.patch`)
6. Copy `product/` (and `sap/`, `cics/`, `tooling/` for CSB) from previous branch
7. Run `cq-camel-prod-maven-plugin` to generate `.mvn/excludes.txt`
8. `mvn -DskipTests clean install`
9. Apply post-patches (`post-*.patch`)
10. Final build to verify

## Key Configuration Files

- `csb-rewrite.yml` -- OpenRewrite recipe adding ~20+ Maven properties and managed dependencies for CSB
- `camel-rewrite.yml` -- OpenRewrite recipe for camel (community version, cq-plugin, prod-maven-plugin)
- `kameletpatches/files.delete` -- List of upstream files to remove from kamelets (CI, docs, infra)

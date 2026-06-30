#!/usr/bin/env python3

import os
import sys
import subprocess
import shutil
import argparse
from rich.console import Console
from rich.panel import Panel

console = Console()

def print_header(text):
    console.print(Panel(f"[bold cyan]{text}[/bold cyan]", expand=False))

def print_success(text):
    console.print(f"[bold green]✓[/bold green] {text}")

def print_info(text):
    console.print(f"[bold blue]ℹ[/bold blue] {text}")

def print_warning(text):
    console.print(f"[bold yellow]⚠[/bold yellow] {text}")

def print_error(text):
    console.print(f"[bold red]✗[/bold red] {text}")

def run_command(cmd, description=None, capture=False):
    if description:
        console.print(f"  [dim]→ {description}[/dim]")
    result = subprocess.run(cmd, capture_output=capture, text=capture)
    if result.returncode == 0 and description:
        console.print(f"  [green]✓[/green] Done")
    return result


def update_pom_properties(pom_path, properties):
    import re
    with open(pom_path, 'r') as f:
        content = f.read()
    for prop, value in properties.items():
        content = re.sub(
            rf"<{re.escape(prop)}>.*</{re.escape(prop)}>",
            f"<{prop}>{value}</{prop}>",
            content,
        )
    with open(pom_path, 'w') as f:
        f.write(content)


def update_parent_version(pom_path, version):
    import re
    with open(pom_path, 'r') as f:
        content = f.read()
    content = re.sub(
        r"(<parent>\s*(?:(?!</?parent>).)*?<version>)([^<]+)(</version>)",
        rf"\g<1>{version}\3",
        content,
        count=1,
        flags=re.DOTALL,
    )
    with open(pom_path, 'w') as f:
        f.write(content)


def create_branch(repo, branch, new_branch, push_branches, version_set, parent_version=None, pom_updates=None, version_set_recursive=False):
    repo_name = repo.rsplit("/", 1)[-1].replace(".git", "")
    console.print(f"\n[bold magenta]{'─' * 60}[/bold magenta]")
    print_info(f"Processing [bold]{repo_name}[/bold]")
    console.print(f"  repo={repo}")
    console.print(f"  branch={branch}  new_branch={new_branch}  push={push_branches}")

    project_dir = os.path.join("maintenance", repo_name)

    run_command(
        ["git", "clone", "-b", branch, repo, project_dir],
        f"Cloning {repo_name} (branch {branch})"
    )

    original_dir = os.getcwd()
    os.chdir(project_dir)

    try:
        run_command(
            ["git", "checkout", "-b", new_branch, f"origin/{branch}"],
            f"Creating branch {new_branch}"
        )

        if version_set:
            art_vers = new_branch.replace("-branch", "")
            art_vers = art_vers.replace("camel-spring-boot-examples-", "")
            art_vers = art_vers.replace("camel-", "")
            snapshot_version = f"{art_vers}-SNAPSHOT"

            run_command(
                [
                    "/usr/local/apache-maven-3.9.9/bin/mvn",
                    f"-DnewVersion={snapshot_version}",
                    "-DgenerateBackupPoms=false",
                    "versions:set",
                ],
                f"Setting version to {snapshot_version}",
            )
            if version_set_recursive:
                import glob
                import re
                old_art_vers = branch.replace("-branch", "")
                old_art_vers = old_art_vers.replace("camel-spring-boot-examples-", "")
                old_art_vers = old_art_vers.replace("camel-", "")
                old_snapshot = f"{old_art_vers}-SNAPSHOT"
                pom_files = sorted(glob.glob("**/pom.xml", recursive=True))
                changed = 0
                for pom_file in pom_files:
                    with open(pom_file, 'r') as f:
                        content = f.read()
                    new_content = content.replace(
                        f"<version>{old_snapshot}</version>",
                        f"<version>{snapshot_version}</version>",
                    )
                    if new_content != content:
                        with open(pom_file, 'w') as f:
                            f.write(new_content)
                        changed += 1
                print_info(f"Recursively updated version in {changed} pom.xml files")

            run_command(
                ["git", "commit", "-a", "-m", f"Change version to {snapshot_version}"],
                "Committing version change",
            )

        if parent_version:
            print_info(f"Setting parent version to {parent_version} in pom.xml")
            update_parent_version("pom.xml", parent_version)
            run_command(
                ["git", "commit", "-a", "-m", f"Change parent version to {parent_version}"],
                "Committing parent version change",
            )

        if pom_updates:
            for update in pom_updates:
                if update.get("recursive"):
                    import glob
                    pom_files = sorted(glob.glob("**/pom.xml", recursive=True))
                    print_info(f"Recursively updating properties in {len(pom_files)} pom.xml files")
                    for pom_path in pom_files:
                        update_pom_properties(pom_path, update["properties"])
                    for prop, value in update["properties"].items():
                        console.print(f"    {prop} = {value}")
                else:
                    pom_path = update["pom"]
                    print_info(f"Updating properties in {pom_path}")
                    update_pom_properties(pom_path, update["properties"])
                    for prop, value in update["properties"].items():
                        console.print(f"    {prop} = {value}")
            run_command(
                ["git", "commit", "-a", "-m", "Update pom properties"],
                "Committing pom property changes",
            )

        if push_branches:
            run_command(
                ["git", "push", "origin", new_branch],
                f"Pushing {new_branch}",
            )
        else:
            print_warning("Skipping push (--no-push or dry run)")

        print_success(f"Done with {repo_name}")
    finally:
        os.chdir(original_dir)


os.environ['JAVA_HOME'] = "/opt/homebrew/Cellar/openjdk@21/21.0.8/libexec/openjdk.jdk/Contents/Home"

if len(sys.argv) < 3 or sys.argv[1] in ("-h", "--help"):
    console.print(Panel("[bold cyan]CSB Create Maintenance Branches[/bold cyan]", expand=False))
    console.print()
    console.print("[bold]Usage:[/bold]  ./create-maintenance-branches.py <version> <previous_version> [--push]")
    console.print()
    console.print("[bold]Arguments:[/bold]")
    console.print("  version           The new version to create branches for (e.g. 4.18.3)")
    console.print("  previous_version  The existing version to branch from (e.g. 4.18.1)")
    console.print()
    console.print("[bold]Options:[/bold]")
    console.print("  --push         Actually push the new branches to the remote repos")
    console.print("                 Without this flag, branches are created locally only (dry run)")
    console.print()
    console.print("[bold]Example:[/bold]")
    console.print("  ./create-maintenance-branches.py 4.18.3 4.18.1         [dim]# dry run, no push[/dim]")
    console.print("  ./create-maintenance-branches.py 4.18.3 4.18.1 --push  [dim]# create and push branches[/dim]")
    console.print()
    console.print("[bold]Repos:[/bold]")
    console.print("  - jboss-fuse/fuse-components")
    console.print("  - jboss-fuse/narayana-spring-boot")
    console.print("  - jboss-fuse/camel-spring-boot-examples")
    console.print("  - jboss-fuse/sap-quickstarts")
    console.print("  - jboss-fuse/camel-launcher")
    console.print("  - jboss-fuse/camel-upgrade-recipes")
    console.print("  - pnc-prod/eclipse-jkube (github.ibm.com)")
    sys.exit(1)

parser = argparse.ArgumentParser(
    description="Create CSB maintenance branches across repos"
)
parser.add_argument("version", help="Full version, e.g. 4.18.3")
parser.add_argument("previous_version", help="Previous version to branch from, e.g. 4.18.1")
parser.add_argument(
    "--push", action="store_true", default=False,
    help="Actually push the new branches (default: dry-run, no push)"
)
args = parser.parse_args()

VERSION = args.version
PREVIOUSVERSION = args.previous_version
PUSH_BRANCHES = args.push

maintenance_dir = "maintenance"
if os.path.exists(maintenance_dir):
    print_info("Cleaning up previous maintenance/ directory")
    shutil.rmtree(maintenance_dir)
os.makedirs(maintenance_dir)

print_header("CSB Create Maintenance Branches")
console.print(f"[bold]Version:[/bold]       {VERSION}")
console.print(f"[bold]Previous version:[/bold] {PREVIOUSVERSION}")
console.print(f"[bold]Push branches:[/bold] {'Yes' if PUSH_BRANCHES else 'No (dry run)'}\n")

repos = [
    {
        "repo": "git@github.com:jboss-fuse/fuse-components.git",
        "branch": f"camel-{PREVIOUSVERSION}-branch",
        "new_branch": f"camel-{VERSION}-branch",
        "version_set": True,
        "parent_version": f"{VERSION}.redhat-00001",
        "pom_updates": [
            {
                "pom": "camel-sap/pom.xml",
                "properties": {
                    "camel-version": f"{VERSION}.redhat-00001",
                    "camel-community-version": VERSION,
                    "camel.sap.plugin.version": f"{VERSION}-SNAPSHOT",
                },
            },
            {
                "pom": "camel-cics/pom.xml",
                "properties": {
                    "camel-version": f"{VERSION}.redhat-00001",
                },
            },
        ],
    },
    {
        "repo": "git@github.com:jboss-fuse/narayana-spring-boot.git",
        "branch": f"3.5.0-camel-{PREVIOUSVERSION}-branch",
        "new_branch": f"3.5.0-camel-{VERSION}-branch",
        "version_set": False,
        "pom_updates": [
            {
                "pom": "pom.xml",
                "properties": {
                    "camel.version": f"{VERSION}.redhat-00001",
                    "camel-spring-boot.version": f"{VERSION}.redhat-00001",
                },
            },
        ],
    },
    {
        "repo": "git@github.com:jboss-fuse/camel-spring-boot-examples.git",
        "branch": f"camel-spring-boot-examples-{PREVIOUSVERSION}-branch",
        "new_branch": f"camel-spring-boot-examples-{VERSION}-branch",
        "version_set": True,
        "version_set_recursive": True,
        "parent_version": f"{VERSION}.redhat-00001",
        "pom_updates": [
            {
                "recursive": True,
                "properties": {
                    "camel-spring-boot-version": f"{VERSION}.redhat-00001",
                    "camel-community-version": VERSION,
                },
            },
        ],
    },
    {
        "repo": "git@github.com:jboss-fuse/sap-quickstarts.git",
        "branch": f"camel-{PREVIOUSVERSION}-branch",
        "new_branch": f"camel-{VERSION}-branch",
        "version_set": True,
        "pom_updates": [
            {
                "pom": "pom.xml",
                "properties": {
                    "camel-version": f"{VERSION}.redhat-00001",
                    "camel-spring-boot-version": f"{VERSION}.redhat-00001",
                    "camel-maven-plugin-version": VERSION,
                },
            },
        ],
    },
    {
        "repo": "git@github.com:jboss-fuse/camel-launcher.git",
        "branch": f"camel-{PREVIOUSVERSION}-branch",
        "new_branch": f"camel-{VERSION}-branch",
        "version_set": True,
        "parent_version": f"{VERSION}.redhat-00001",
        "pom_updates": [
            {
                "pom": "pom.xml",
                "properties": {
                    "camel-version": f"{VERSION}.redhat-00001",
                    "camel-community-version": VERSION,
                    "camel-spring-boot-version": f"{VERSION}.redhat-00001",
                    "camel-kamelets-version": f"{VERSION}.redhat-00001",
                },
            },
        ],
    },
    {
        "repo": "git@github.com:jboss-fuse/camel-upgrade-recipes.git",
        "branch": f"camel-{PREVIOUSVERSION}-branch",
        "new_branch": f"camel-{VERSION}-branch",
        "version_set": True,
        "pom_updates": [
            {
                "pom": "pom.xml",
                "properties": {
                    "camel-version": f"{VERSION}.redhat-00001",
                    "camel-spring-boot-version": f"{VERSION}.redhat-00001",
                },
            },
        ],
    },
    {
        "repo": "git@github.ibm.com:pnc-prod/eclipse-jkube.git",
        "branch": f"1.19.0-camel-{PREVIOUSVERSION}",
        "new_branch": f"1.19.0-camel-{VERSION}",
        "version_set": False,
    },
]

failed = []
for i, r in enumerate(repos, 1):
    console.print(f"\n[bold green]Repo {i}/{len(repos)}[/bold green]")
    try:
        create_branch(r["repo"], r["branch"], r["new_branch"], PUSH_BRANCHES, r["version_set"], r.get("parent_version"), r.get("pom_updates"), r.get("version_set_recursive", False))
    except Exception as e:
        print_error(f"Failed: {e}")
        failed.append(r["repo"])

console.print("\n")
if failed:
    print_header("⚠ Completed with errors")
    for f in failed:
        console.print(f"  [red]✗[/red] {f}")
else:
    print_header("✓ All maintenance branches created!")
    if not PUSH_BRANCHES:
        print_warning("Branches were NOT pushed. Re-run with --push to push them.")

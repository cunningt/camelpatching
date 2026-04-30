#!/usr/bin/env python3

import os
import sys
import subprocess
import time
import argparse
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

console = Console()

# Track failed patches
failed_patches = []
partial_patches = []

def print_header(text):
    """Print a styled header"""
    console.print(Panel(f"[bold cyan]{text}[/bold cyan]", expand=False))

def print_step(step_num, total_steps, description):
    """Print a step indicator"""
    console.print(f"\n[bold green]Step {step_num}/{total_steps}:[/bold green] {description}")

def print_success(text):
    """Print a success message"""
    console.print(f"[bold green]✓[/bold green] {text}")

def print_info(text):
    """Print an info message"""
    console.print(f"[bold blue]ℹ[/bold blue] {text}")

def print_warning(text):
    """Print a warning message"""
    console.print(f"[bold yellow]⚠[/bold yellow] {text}")

def print_error(text):
    """Print an error message"""
    console.print(f"[bold red]✗[/bold red] {text}")

def run_command(cmd, description=None, env=None):
    """Run a command with optional description"""
    if description:
        console.print(f"  [dim]→ {description}[/dim]")
    result = subprocess.run(cmd, env=env if env else os.environ)
    if result.returncode == 0 and description:
        console.print(f"  [green]✓[/green] Done")
    return result

def apply_patch(patch_file, debug=False, use_reject_mode=False):
    """Apply a patch file with optional debug prompting and error handling"""
    if debug:
        console.print(f"\n[bold yellow]Ready to apply:[/bold yellow] {patch_file.name}")
        console.print(f"[dim]Path:[/dim] {patch_file}")
        input("[bold cyan]Press Enter to apply this patch...[/bold cyan] ")

    print_info(f"Applying {patch_file.name}")

    # First, check if the patch will apply cleanly
    check_result = subprocess.run(
        ["git", "apply", "--check", str(patch_file)],
        capture_output=True,
        text=True
    )

    if check_result.returncode == 0:
        # Patch should apply cleanly, use git am
        with open(patch_file, 'r') as f:
            am_result = subprocess.run(
                ["git", "am", "--keep-cr", "--signoff"],
                stdin=f,
                capture_output=True,
                text=True
            )

        if am_result.returncode == 0:
            print_success(f"Applied {patch_file.name}")
        else:
            # git am failed, try to recover
            print_error(f"Failed to apply {patch_file.name} via git am")
            console.print(f"  [red]{am_result.stderr}[/red]")
            failed_patches.append((patch_file.name, "git am failed"))
            # Abort the am to clean up
            subprocess.run(["git", "am", "--abort"], capture_output=True)
    else:
        # Patch won't apply cleanly
        print_warning(f"Patch {patch_file.name} has conflicts")
        console.print(f"  [yellow]Check output:[/yellow]")
        console.print(f"  [dim]{check_result.stderr}[/dim]")

        if use_reject_mode:
            # Use --reject mode (creates .rej files)
            console.print(f"  [cyan]Using --reject mode (creates .rej files)...[/cyan]")
            reject_result = subprocess.run(
                ["git", "apply", "--reject", "--whitespace=fix", str(patch_file)],
                capture_output=True,
                text=True
            )

            if reject_result.returncode == 0:
                # Check for .rej files
                rej_files = list(Path('.').rglob('*.rej'))

                if rej_files:
                    print_warning(f"Partially applied {patch_file.name}")
                    console.print(f"  [yellow]Rejected hunks saved to .rej files:[/yellow]")
                    for rej in rej_files:
                        console.print(f"    - {rej}")
                        partial_patches.append(f"{patch_file.name} -> {rej}")
                else:
                    print_success(f"Applied {patch_file.name} (with whitespace fixes)")

                # Stage the changes
                subprocess.run(["git", "add", "-u"], capture_output=True)

                # Commit what we could apply
                commit_msg = f"Partial application of {patch_file.name}\n\nSome hunks were rejected." if rej_files else f"Apply {patch_file.name}"
                subprocess.run(
                    ["git", "commit", "-m", commit_msg],
                    capture_output=True
                )
            else:
                print_error(f"Could not apply any part of {patch_file.name}")
                console.print(f"  [red]{reject_result.stderr}[/red]")
                failed_patches.append((patch_file.name, "Complete failure"))
        else:
            # Try 3-way merge (creates VS Code-friendly conflict markers)
            console.print(f"  [cyan]Attempting 3-way merge (creates conflict markers for VS Code)...[/cyan]")

            with open(patch_file, 'r') as f:
                threeway_result = subprocess.run(
                    ["git", "am", "--3way", "--keep-cr"],
                    stdin=f,
                    capture_output=True,
                    text=True
                )

            if threeway_result.returncode != 0:
                # 3-way merge had conflicts - check if we have conflict markers in files
                status_result = subprocess.run(
                    ["git", "status", "--short"],
                    capture_output=True,
                    text=True
                )

                if "UU " in status_result.stdout or "AA " in status_result.stdout:
                    # We have merge conflicts with markers - perfect for VS Code
                    print_warning(f"Merge conflicts in {patch_file.name} - conflict markers added")
                    console.print(f"  [cyan]Files with conflicts (open in VS Code to resolve):[/cyan]")

                    conflicted_files = []
                    for line in status_result.stdout.split('\n'):
                        if line.startswith('UU ') or line.startswith('AA '):
                            file_path = line[3:].strip()
                            conflicted_files.append(file_path)
                            console.print(f"    - {file_path}")

                    partial_patches.append(f"{patch_file.name} (conflicts in {len(conflicted_files)} file(s))")

                    # Abort the am to allow manual resolution
                    subprocess.run(["git", "am", "--abort"], capture_output=True)

                    # Now try --reject as fallback to apply what we can
                    console.print(f"  [yellow]Applying with --reject as fallback...[/yellow]")
                    reject_result = subprocess.run(
                        ["git", "apply", "--reject", "--whitespace=fix", str(patch_file)],
                        capture_output=True,
                        text=True
                    )

                    if reject_result.returncode == 0:
                        # Check for .rej files
                        rej_files = list(Path('.').rglob('*.rej'))

                        if rej_files:
                            console.print(f"  [yellow]Rejected hunks saved to .rej files:[/yellow]")
                            for rej in rej_files:
                                console.print(f"    - {rej}")

                        # Stage the changes
                        subprocess.run(["git", "add", "-u"], capture_output=True)

                        # Commit what we could apply
                        subprocess.run(
                            ["git", "commit", "-m", f"Partial application of {patch_file.name}\n\nConflicts need manual resolution. Open files in VS Code to resolve."],
                            capture_output=True
                        )
                    else:
                        print_error(f"Could not apply any part of {patch_file.name}")
                        failed_patches.append((patch_file.name, "Complete failure"))
                else:
                    # Some other error with git am --3way
                    print_error(f"Failed to apply {patch_file.name}")
                    console.print(f"  [red]{threeway_result.stderr}[/red]")
                    failed_patches.append((patch_file.name, "3-way merge failed"))
                    subprocess.run(["git", "am", "--abort"], capture_output=True)
            else:
                # 3-way merge succeeded!
                print_success(f"Applied {patch_file.name} (via 3-way merge)")

# Set JAVA_HOME
os.environ['JAVA_HOME'] = "/opt/homebrew/Cellar/openjdk@21/21.0.8/libexec/openjdk.jdk/Contents/Home"

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Camel Spring Boot patching automation script')
parser.add_argument('endpoint', nargs='?', default='',
                    help='Endpoint to stop at (endbeforepre, endbeforepost)')
parser.add_argument('--debug', action='store_true',
                    help='Apply patches one by one with user prompts')
parser.add_argument('--use-reject', action='store_true',
                    help='Use git apply --reject instead of 3-way merge for conflicts (creates .rej files)')
args = parser.parse_args()

endpoint = args.endpoint
debug_mode = args.debug
use_reject = args.use_reject

# Configuration
vers = "4.19.0"
dir_name = f"camel-spring-boot-{vers}-branch"
patchdir = "csbpatches"

upstreambranch = f"camel-spring-boot-{vers}"
currentprodbranch = "camel-spring-boot-4.18.1-branch"
prodlocation = "csbprodlocation"

# Print welcome banner
print_header("Camel Spring Boot Patching Script")
console.print(f"[bold]Version:[/bold] {vers}")
console.print(f"[bold]Endpoint:[/bold] {endpoint if endpoint else 'Full build'}")
console.print(f"[bold]Debug mode:[/bold] {'Enabled' if debug_mode else 'Disabled'}")
console.print(f"[bold]Conflict handling:[/bold] {'Reject mode (.rej files)' if use_reject else '3-way merge (VS Code markers)'}\n")

# Clean up directories
print_step(1, 9, "Cleaning up directories")
run_command(["rm", "-rf", dir_name], f"Removing {dir_name}")
run_command(["rm", "-rf", prodlocation], f"Removing {prodlocation}")

# Clone
print_step(2, 9, "Cloning repositories")
run_command(["git", "clone", "git@github.com:jboss-fuse/camel-spring-boot.git", dir_name],
            f"Cloning jboss-fuse/camel-spring-boot into {dir_name}")
run_command(["git", "clone", "-b", currentprodbranch, "git@github.com:jboss-fuse/camel-spring-boot.git", prodlocation],
            f"Cloning {currentprodbranch} into {prodlocation}")

# system("cp -r ~/prod/camel-spring-boot $prodlocation");

print_step(3, 9, "Setting up git remotes and fetching")
os.chdir(dir_name)
run_command(["git", "remote", "add", "upstream", "git@github.com:apache/camel-spring-boot.git"],
            "Adding upstream remote")
run_command(["git", "fetch", "upstream"], "Fetching upstream")
run_command(["git", "fetch", "upstream", "--tags"], "Fetching upstream tags")

time.sleep(10)

run_command(["git", "checkout", "-b", f"camel-spring-boot-{vers}-branch", upstreambranch],
            f"Creating branch camel-spring-boot-{vers}-branch")

time.sleep(3)

# Change the version
print_step(4, 9, "Updating Maven version")
run_command([
    "/usr/local/apache-maven-3.9.9/bin/mvn",
    f"-DnewVersion={vers}-SNAPSHOT",
    "-DgenerateBackupPoms=false",
    "versions:set"
], f"Setting version to {vers}-SNAPSHOT", env=os.environ)

run_command(["git", "commit", "-a", "-m", f"Change versions to {vers}-SNAPSHOT"],
            "Committing version changes")

# Copy and run rewrite
print_info("Running OpenRewrite")
run_command(["cp", "../csb-rewrite.yml", "./rewrite.yml"], "Copying rewrite.yml")
run_command([
    "/usr/local/apache-maven-3.9.9/bin/mvn",
    "-N",
    "-U",
    "org.openrewrite.maven:rewrite-maven-plugin:run",
    "-Drewrite.activeRecipes=com.redhat.camel-spring-boot.AddProductBranchProperties"
], "Running rewrite plugin", env=os.environ)

if "endbeforepre" in endpoint:
    print_success("Stopping before pre-patches (endbeforepre)")
    sys.exit(0)

# Note: pre-patches section is commented out in original script

# Copy product directories
print_step(5, 9, "Copying product directories")
console.print("\n  [dim]→ Copying product directory[/dim]")
subprocess.run(["cp", "-r", f"../{prodlocation}/product", "."])
subprocess.run(["git", "add", "product"])
print_success("Product directory copied")

time.sleep(3)

console.print("  [dim]→ Copying sap directory[/dim]")
subprocess.run(["cp", "-r", f"../{prodlocation}/sap", "."])
subprocess.run(["git", "add", "sap"])
print_success("SAP directory copied")

console.print("  [dim]→ Copying cics directory[/dim]")
subprocess.run(["cp", "-r", f"../{prodlocation}/cics", "."])
subprocess.run(["git", "add", "cics"])
print_success("CICS directory copied")

# Run prod-maven-plugin
print_step(6, 9, "Running prod-maven-plugin")
run_command([
    "/usr/local/apache-maven-3.9.9/bin/mvn",
    "org.l2x6.cq:cq-camel-spring-boot-prod-maven-plugin:camel-spring-boot-prod-excludes",
    "-N"
], "Executing camel-spring-boot-prod-excludes", env=os.environ)

time.sleep(3)

run_command(["git", "add", ".mvn/excludes.txt"], "Adding excludes.txt")
run_command(["git", "commit", "-a", "-m", "Run prod-maven-plugin for the first time"],
            "Committing plugin results")

print_info("Building with Maven (this may take a while...)")
run_command([
    "/usr/local/apache-maven-3.9.9/bin/mvn",
    "-DskipTests",
    "clean",
    "install"
], "Running mvn clean install", env=os.environ)

time.sleep(3)

run_command(["git", "commit", "-a", "-m", "Compile with results of prod-maven-plugin"],
            "Committing compilation results")

if "endbeforepost" in endpoint:
    print_success("Stopping before post-patches (endbeforepost)")
    sys.exit(0)

# Apply post-prod-maven-plugin patches, with check
print_step(7, 9, "Applying post-prod-maven-plugin patches")
patch_files = sorted(Path(f"../{patchdir}").glob("post-*.patch"))
if patch_files:
    for patch_file in patch_files:
        apply_patch(patch_file, debug=debug_mode, use_reject_mode=use_reject)
else:
    console.print("  [yellow]No post-patches found[/yellow]")

time.sleep(3)

if "endafterpost" in endpoint:
    print_success("Stopping after post-patches (endafterpost)")
    sys.exit(0)

# Apply tooling changes
print_step(8, 9, "Copying tooling files")
console.print("  [dim]→ Copying tooling pom.xml[/dim]")
subprocess.run(["cp", "-r", f"../{prodlocation}/tooling/pom.xml", "./tooling"])
console.print("  [dim]→ Copying redhat-camel-spring-boot-bom-generator[/dim]")
subprocess.run(["cp", "-r", f"../{prodlocation}/tooling/redhat-camel-spring-boot-bom-generator", "./tooling"])
console.print("  [dim]→ Copying redhat-patch-maven-plugin[/dim]")
subprocess.run(["cp", "-r", f"../{prodlocation}/tooling/redhat-patch-maven-plugin", "./tooling"])

time.sleep(3)

# Update tooling versions
print_info("Updating tooling versions")
run_command([
    "/usr/local/apache-maven-3.9.9/bin/mvn",
    f"-DnewVersion={vers}-SNAPSHOT",
    "-DgenerateBackupPoms=false",
    "-f", "tooling/pom.xml",
    "versions:set"
], f"Setting tooling version to {vers}-SNAPSHOT", env=os.environ)

time.sleep(15)

subprocess.run(["git", "add", "tooling"])

time.sleep(15)

run_command(["git", "commit", "-a", "-m", "Compile with results of prod-maven-plugin"],
            "Committing tooling changes")

# Build for final time - there should be no changes
print_step(9, 9, "Final build")
print_info("Running final Maven build (this may take a while...)")
run_command([
    "/usr/local/apache-maven-3.9.9/bin/mvn",
    "-DskipTests",
    "clean",
    "install"
], "Running mvn clean install", env=os.environ)

run_command(["git", "commit", "-a", "-m", "Build and refresh tooling"],
            "Committing final build results")

console.print("\n")

# Print summary
if failed_patches or partial_patches:
    print_header("⚠ Camel Spring Boot Patching Complete with Issues")
    console.print(f"[bold yellow]Built Camel Spring Boot {vers} but some patches need attention[/bold yellow]\n")

    if partial_patches:
        console.print("[bold yellow]Partially Applied Patches:[/bold yellow]")
        console.print("[dim]These patches were applied but had conflicts. Check .rej files for rejected hunks.[/dim]")
        for patch_info in partial_patches:
            console.print(f"  [yellow]•[/yellow] {patch_info}")
        console.print()

    if failed_patches:
        console.print("[bold red]Failed Patches:[/bold red]")
        console.print("[dim]These patches could not be applied at all.[/dim]")
        for patch_name, reason in failed_patches:
            console.print(f"  [red]✗[/red] {patch_name} - {reason}")
        console.print()

    console.print("[bold cyan]Next Steps:[/bold cyan]")
    console.print("  1. Open the project in VS Code: [dim]code .[/dim]")
    console.print("  2. Look for files with conflict markers ([yellow]<<<<<<<[/yellow], [yellow]=======[/yellow], [yellow]>>>>>>>[/yellow])")
    console.print("  3. Use VS Code's merge editor to resolve conflicts")
    console.print("  4. Review .rej files for any rejected patch hunks")
    console.print("  5. Stage and commit the manual fixes: [dim]git add . && git commit[/dim]")
    console.print("  6. Run the final build to verify everything works\n")
else:
    print_header("✓ Camel Spring Boot Patching Complete!")
    console.print(f"[bold green]Successfully built Camel Spring Boot {vers}[/bold green]")
    console.print(f"[bold green]All patches applied cleanly![/bold green]\n")

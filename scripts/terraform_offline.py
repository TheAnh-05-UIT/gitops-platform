"""Validate the reviewed Terraform lab, bootstrap, and modules in temporary copies."""

import argparse
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile


LAB = Path("lab")
BOOTSTRAP = Path("bootstrap")
INVENTORY = Path("modules/ansible-inventory")
AWS_MODULES = tuple(Path("modules") / name for name in ("compute", "iam", "networking", "security"))
SUITES = (LAB, BOOTSTRAP, INVENTORY, *AWS_MODULES)
SOURCE = Path(__file__).resolve().parents[1] / "infra/terraform"
AWS_PROVIDER = "registry.terraform.io/hashicorp/aws"
BACKEND_SOURCE = 'terraform { backend "s3" { encrypt = true use_lockfile = true } }'
TOKEN = re.compile(
    r'(?P<ignored>\s+|\#[^\n]*|//[^\n]*|/\*[\s\S]*?\*/)'
    r'|"(?:[^"\\]|\\.)*"|[a-zA-Z_][\w-]*|\S'
)
NAME = re.compile(r'[a-zA-Z_][\w-]*')


class UnsafeSource(ValueError):
    """The copied Terraform source exceeded the supported offline contract."""


def tokens(text):
    return [match[0] for match in TOKEN.finditer(text) if not match["ignored"]]


def blocks(items, kind):
    """Find relevant HCL blocks without evaluating Terraform expressions."""
    for start, token in enumerate(items):
        if token != kind or (start > 0 and items[start - 1] == "."):
            continue
        body_start = start + 1
        while body_start < len(items) and (
            items[body_start].startswith('"') or NAME.fullmatch(items[body_start])
        ):
            body_start += 1
        if body_start == len(items) or items[body_start] != "{":
            continue
        depth = 1
        for end in range(body_start + 1, len(items)):
            if items[end] == "{":
                depth += 1
            elif items[end] == "}":
                depth -= 1
            if depth == 0:
                yield items[start + 1:body_start], items[body_start + 1:end]
                break
        else:
            raise UnsafeSource(f"Incomplete {kind} block.")


def attributes(items, name):
    """Read direct attribute values, skipping nested attributes."""
    depth = 0
    for index, token in enumerate(items[:-2]):
        if token in ("{", "[", "("):
            depth += 1
        elif token in ("}", "]", ")"):
            depth -= 1
        elif depth == 0 and token in (name, f'"{name}"') and items[index + 1] == "=":
            yield items[index + 2]


def check_config(content, suite, filename):
    items = tokens(content)
    if suite == LAB and filename == "backend.tf":
        if items != tokens(BACKEND_SOURCE):
            raise UnsafeSource("Unexpected production backend declaration in lab/backend.tf.")
        return
    if any(list(blocks(items, kind)) for kind in ("backend", "cloud", "data", "provisioner")):
        raise UnsafeSource(f"Unsupported backend, cloud, data source or provisioner in {filename}.")
    for labels, body in blocks(items, "provider"):
        if (
            suite not in (LAB, BOOTSTRAP)
            or labels != ['"aws"']
            or list(attributes(body, "alias"))
        ):
            raise UnsafeSource(f"Unexpected provider configuration in {filename}.")
    approved_modules = {f'"../{child.as_posix()}"' for child in (INVENTORY, *AWS_MODULES)}
    for _, body in blocks(items, "module"):
        source = list(attributes(body, "source"))
        if suite != LAB or len(source) != 1 or source[0] not in approved_modules:
            raise UnsafeSource(f"Module source outside the approved local modules in {filename}.")
        if list(attributes(body, "providers")):
            raise UnsafeSource(f"Module provider override in {filename}.")


def check_test(content, filename, uses_aws):
    items = tokens(content)
    if any(list(blocks(items, kind)) for kind in ("provider", "module", "data", "provisioner", "backend", "cloud")):
        raise UnsafeSource(f"Unsupported test dependency in {filename}.")
    mocks = list(blocks(items, "mock_provider"))
    if [labels for labels, _ in mocks] != ([['"aws"']] if uses_aws else []):
        raise UnsafeSource(f"Expected an explicit unaliased AWS mock where used in {filename}.")
    for _, body in mocks:
        if any(list(attributes(body, setting)) for setting in ("source", "alias")):
            raise UnsafeSource(f"Unexpected mock provider source or alias in {filename}.")
    runs = list(blocks(items, "run"))
    if not runs or any(
        list(attributes(body, "command")) != ["plan"] or list(attributes(body, "providers"))
        for _, body in runs
    ):
        raise UnsafeSource(f"Every run must explicitly select plan with its default mock in {filename}.")


def copy_sources(source, destination):
    for suite in SUITES:
        root = source / suite
        test_dir = root / "tests"
        if not test_dir.is_dir():
            raise UnsafeSource(f"Missing tests for {suite}.")
        files = [
            *root.glob("*.tf"),
            *root.glob("*.tftest.hcl"),
            *(root / "examples").glob("*.tfvars.json.example"),
            *test_dir.glob("*.tftest.hcl"),
            *(test_dir / "fixtures").glob("*.json"),
        ]
        if suite != INVENTORY:
            lock_root = root if suite in (LAB, BOOTSTRAP) else source / LAB
            files.append(lock_root / ".terraform.lock.hcl")
        if any(root.glob("*.tf.json")) or any(root.glob("*.tftest.json")) or any(test_dir.glob("*.tftest.json")):
            raise UnsafeSource(f"Unsupported JSON Terraform configuration or test in {suite}.")
        for file in files:
            if file.name == "override.tf" or file.name.endswith("_override.tf"):
                continue
            if file.is_symlink() or not file.resolve().is_relative_to(source):
                raise UnsafeSource(f"Source file outside the reviewed tree for {suite}.")
            target = destination / suite / (
                Path(file.name) if file.name == ".terraform.lock.hcl" else file.relative_to(root)
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, target)


def verify_sources(source):
    if not (source / LAB / "backend.tf").is_file():
        raise UnsafeSource("Missing reviewed production backend declaration.")
    for suite in SUITES:
        directory = source / suite
        for path in directory.glob("*.tf"):
            check_config(path.read_text(encoding="utf-8"), suite, path.name)
        tests = sorted([*directory.glob("*.tftest.hcl"), *(directory / "tests").glob("*.tftest.hcl")])
        if not tests:
            raise UnsafeSource(f"No copied Terraform tests for {suite}.")
        for path in tests:
            check_test(path.read_text(encoding="utf-8"), path.name, suite != INVENTORY)


def offline_environment(scratch, inherited):
    env = {key: value for key, value in inherited.items() if not key.upper().startswith(("AWS_", "TF_"))}
    for key, filename in (
        ("AWS_CONFIG_FILE", "aws-config"),
        ("AWS_SHARED_CREDENTIALS_FILE", "aws-credentials"),
        ("TF_CLI_CONFIG_FILE", "cli.tfrc"),
    ):
        path = scratch / filename
        path.touch(exist_ok=False)
        env[key] = str(path)
    env.update(CHECKPOINT_DISABLE="1", AWS_EC2_METADATA_DISABLED="true")
    return env


def local_package(mirror, source):
    lockfiles = [(source / suite / ".terraform.lock.hcl").read_bytes() for suite in (LAB, BOOTSTRAP)]
    if lockfiles[0] != lockfiles[1]:
        raise UnsafeSource("The lab and bootstrap provider locks differ.")
    lock = tokens(lockfiles[0].decode("utf-8"))
    providers = list(blocks(lock, "provider"))
    if [labels for labels, _ in providers] != [[f'"{AWS_PROVIDER}"']]:
        raise UnsafeSource("Expected only the locked HashiCorp AWS provider.")
    version = list(attributes(providers[0][1], "version"))
    if len(version) != 1 or not re.fullmatch(r'"[0-9]+\.[0-9]+\.[0-9]+"', version[0]):
        raise UnsafeSource("Could not read the locked AWS provider version.")
    os_name = platform.system().lower()
    arch = {"amd64": "amd64", "x86_64": "amd64", "arm64": "arm64", "aarch64": "arm64"}.get(
        platform.machine().lower()
    )
    if os_name not in ("windows", "linux", "darwin") or arch is None:
        raise UnsafeSource("This host does not have a supported runner OS and architecture.")
    relative = Path(AWS_PROVIDER) / version[0].strip('"') / f"{os_name}_{arch}"
    package = mirror / relative
    if not package.is_dir() or not list(package.glob("terraform-provider-aws*")):
        raise UnsafeSource(f"Missing unpacked locked provider package for {relative}.")
    return relative


def link_package(scratch, mirror, package):
    """Reuse the verified package without duplicating the provider for every suite."""
    original = mirror / package
    shared = scratch / "mirror-cache"
    for suite in SUITES:
        if suite == INVENTORY:
            continue
        destination = scratch / "data" / suite / "providers" / package
        destination.mkdir(parents=True)
        for file in original.iterdir():
            if not file.is_file():
                continue
            target = destination / file.name
            try:
                os.link(file, target)
            except OSError:
                shared.mkdir(exist_ok=True)
                local = shared / file.name
                if not local.is_file():
                    shutil.copy2(file, local)
                os.link(local, target)


def run_suite(scratch, suite, mirror, environment, execute=subprocess.run):
    directory = scratch / "source" / suite
    env = dict(environment, TF_DATA_DIR=str(scratch / "data" / suite))
    print(f"Offline suite {suite.as_posix()}", flush=True)
    execute(
        ["terraform", "init", "-backend=false", "-lockfile=readonly", "-input=false",
         "-no-color", f"-plugin-dir={mirror}"],
        cwd=directory, env=env, check=True,
    )
    execute(["terraform", "validate", "-no-color"], cwd=directory, env=env, check=True)
    if suite == LAB:
        with (directory / "zz_offline_override.tf").open("x", encoding="ascii") as stream:
            stream.write('terraform {\n  backend "local" {}\n}\n')
    execute(["terraform", "test", "-no-color"], cwd=directory, env=env, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider-mirror", type=Path, required=True, help="Approved unpacked local provider mirror")
    args = parser.parse_args()
    mirror = args.provider_mirror.resolve()
    try:
        if not mirror.is_dir():
            raise UnsafeSource("The approved provider mirror is not a directory.")
        with tempfile.TemporaryDirectory(prefix="gitops-terraform-offline-") as workdir:
            scratch = Path(workdir).resolve()
            source = scratch / "source"
            environment = offline_environment(scratch, os.environ)
            copy_sources(SOURCE, source)
            verify_sources(source)
            package = local_package(mirror, source)
            link_package(scratch, mirror, package)
            subprocess.run(
                ["terraform", "fmt", "-check", "-recursive", "-no-color"],
                cwd=source, env=environment, check=True,
            )
            for suite in SUITES:
                run_suite(scratch, suite, mirror, environment)
    except (UnsafeSource, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Offline Terraform validation stopped. {exc}\n")


if __name__ == "__main__":
    main()

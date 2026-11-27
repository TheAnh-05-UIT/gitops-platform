"""Render a private Terraform backend file after checking the approved environment."""

import argparse
import json
from pathlib import Path
import re


def load_object(path):
    with path.open(encoding="utf-8-sig") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError("Both inputs must be JSON objects.")
    return value


def render_backend(manifest, lab_vars, approved_account):
    project = lab_vars.get("project_name", "gitops-platform")
    environment = lab_vars.get("environment", "lab")
    region = lab_vars.get("aws_region")
    for value, maximum in ((project, 32), (environment, 16)):
        if not isinstance(value, str) or len(value) > maximum or not re.fullmatch(
            r"[a-z][a-z0-9]*(-[a-z0-9]+)*", value
        ):
            raise ValueError("Invalid lab project or environment.")
    if not isinstance(region, str) or not re.fullmatch(r"[a-z]{2}(-[a-z]+)+-[1-9][0-9]*", region):
        raise ValueError("Supply the approved Region in the lab variable file.")
    if not re.fullmatch(r"[0-9]{12}", approved_account):
        raise ValueError("Invalid approved AWS account ID.")

    prefix = f"terraform-state/{project}/{environment}"
    key = f"{prefix}/terraform.tfstate"
    expected = {
        "project_name": project,
        "environment": environment,
        "region": region,
        "account_id": approved_account,
        "key": key,
        "lock_key": f"{key}.tflock",
        "workspace_key_prefix": f"{prefix}/workspaces",
    }
    if any(manifest.get(field) != value for field, value in expected.items()):
        raise ValueError("Bootstrap metadata does not match the approved account, lab variables and key layout.")
    if manifest.get("encrypt") is not True or manifest.get("use_lockfile") is not True:
        raise ValueError("The bootstrap output must require encryption and native locking.")

    bucket = manifest.get("bucket")
    if (
        not isinstance(bucket, str)
        or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket)
        or bucket.startswith(("xn--", "sthree-", "amzn-s3-demo-"))
        or bucket.endswith(("-s3alias", "--ol-s3", "--x-s3", "--table-s3", "-an"))
    ):
        raise ValueError("Invalid general-purpose state bucket name.")

    settings = {
        "bucket": bucket,
        "key": key,
        "region": region,
        "workspace_key_prefix": expected["workspace_key_prefix"],
        "allowed_account_ids": [approved_account],
        "encrypt": True,
        "use_lockfile": True,
    }
    return "".join(f"{field:20} = {json.dumps(value)}\n" for field, value in settings.items())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap-output", required=True, type=Path)
    parser.add_argument("--lab-tfvars", required=True, type=Path)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.out.suffix != ".tfbackend":
            raise ValueError("The output path must end with .tfbackend.")
        text = render_backend(load_object(args.bootstrap_output), load_object(args.lab_tfvars), args.account_id)
        with args.out.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    except FileExistsError:
        parser.exit(1, "Backend file already exists. Choose a fresh protected path.\n")
    except json.JSONDecodeError:
        parser.exit(1, "Invalid backend manifest or lab variable JSON.\n")
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")
    except OSError:
        parser.exit(1, "Unable to read or write a protected backend configuration file.\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Read a deployed stack and write a retention-only update; never mutate AWS."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--profile")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cli = ["aws", "--region", args.region]
    if args.profile:
        cli += ["--profile", args.profile]

    def read(*arguments):
        return json.loads(subprocess.check_output(cli + list(arguments), text=True))

    template = read("cloudformation", "get-template", "--stack-name", args.stack,
                    "--template-stage", "Original")["TemplateBody"]
    if isinstance(template, str):
        try:
            template = json.loads(template)
        except json.JSONDecodeError:
            try:
                import yaml
            except ImportError as error:
                raise SystemExit("YAML template: rerun with uv run --with pyyaml python scripts/prepare-terraform-retain.py ...") from error

            class CloudFormationLoader(yaml.SafeLoader):
                pass

            def intrinsic(loader, tag, node):
                if isinstance(node, yaml.ScalarNode):
                    value = loader.construct_scalar(node)
                elif isinstance(node, yaml.SequenceNode):
                    value = loader.construct_sequence(node)
                else:
                    value = loader.construct_mapping(node)
                if tag == "GetAtt" and isinstance(value, str):
                    value = value.split(".", 1)
                return {tag if tag in {"Ref", "Condition"} else "Fn::" + tag: value}

            CloudFormationLoader.add_multi_constructor("!", intrinsic)
            template = yaml.load(template, Loader=CloudFormationLoader)
    stack = read("cloudformation", "describe-stacks", "--stack-name", args.stack)["Stacks"][0]
    inventory = read("cloudformation", "list-stack-resources", "--stack-name", args.stack)
    for resource in template["Resources"].values():
        resource.update(DeletionPolicy="Retain", UpdateReplacePolicy="Retain")
    parameters = [{"ParameterKey": p["ParameterKey"], "UsePreviousValue": True}
                  for p in stack.get("Parameters", [])]
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Parameters contain only keys, never values or NoEcho secrets.
    for name, value in [("retain.json", template), ("parameters.json", parameters),
                        ("resources.json", inventory)]:
        path = args.output / name
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
    print(f"Prepared retention-only update for {args.stack}; AWS was not changed.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Read a deployed stack and write a retention-only update; never mutate AWS."""
import argparse
import json
import os
from pathlib import Path
import re
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
    yaml_body = None
    if isinstance(template, str):
        try:
            template = json.loads(template)
        except json.JSONDecodeError:
            yaml_body = template
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
    # Preserve YAML intrinsic syntax: reserializing !GetAtt from scalar to list
    # can produce a spurious DirectModification in a CloudFormation change set.
    if yaml_body is not None:
        lines = []
        inside = False
        count = 0
        for line in yaml_body.splitlines():
            if line == "Resources:":
                inside = True
            elif inside and re.match(r"^\S", line):
                inside = False
            if inside and re.match(r"^    (DeletionPolicy|UpdateReplacePolicy):", line):
                continue
            lines.append(line)
            if inside and re.match(r"^  [A-Za-z0-9]+:$", line):
                lines.extend(["    DeletionPolicy: Retain", "    UpdateReplacePolicy: Retain"])
                count += 1
        if count != len(template["Resources"]):
            raise SystemExit("Unsupported YAML indentation; no retention template written.")
        template_name, template_text = "retain.yaml", "\n".join(lines) + "\n"
    else:
        template_name, template_text = "retain.json", json.dumps(template, indent=2) + "\n"
    fd = os.open(args.output / template_name, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(template_text)
    # Parameters contain only keys, never values or NoEcho secrets.
    for name, value in [("parameters.json", parameters), ("resources.json", inventory)]:
        path = args.output / name
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
    print(f"Prepared {args.output / template_name} for {args.stack}; AWS was not changed.")


if __name__ == "__main__":
    main()

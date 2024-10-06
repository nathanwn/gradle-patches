import argparse
import logging
import logging.config
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Mapping

from ruamel.yaml import YAML

logger = logging.getLogger(sys.argv[0])


def configure_logging(verbose: bool) -> None:
    """Configure logging."""
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "[%(levelname)s|%(module)s]: %(message)s",
                },
                "verbose": {
                    "format": "[%(levelname)s|%(module)s|L%(lineno)d]: %(message)s",
                },
            },
            "handlers": {
                "stderr": {
                    "class": "logging.StreamHandler",
                    "level": "DEBUG" if verbose else "INFO",
                    "formatter": "verbose" if verbose else "standard",
                    "stream": "ext://sys.stderr",
                },
            },
            "root": {
                "level": "DEBUG",
                "handlers": ["stderr"],
            },
        }
    )


def patch_env(patch: Mapping[str, str | None]) -> dict[str, str]:
    """Patch env."""
    copied_env = dict(os.environ)  # Make a copy.

    for var, value in patch.items():
        if value is None:
            copied_env.pop(var, None)
        else:
            copied_env[var] = value

    return copied_env


def build(version: str) -> int:
    yaml = YAML()
    patch_config_file = f"./patches/{version}/patch.yml"
    with open(patch_config_file) as f:
        config = yaml.load(f)
        logger.info("Loaded %s", patch_config_file)

    subprocess.run(
        args=["git", "restore", "."],
        cwd="gradle",
        check=True,
    )

    subprocess.run(
        args=["git", "checkout", config["tag"]],
        cwd="gradle",
        check=True,
    )

    for patch in config["patches"]:
        result = subprocess.run(
            args=[
                *("git", "apply"),
                os.path.join("..", "patches", version, patch),
            ],
            cwd="gradle",
        )
        if result.returncode != 0:
            return 1

    for cmd in config["cmds"]:
        args = cmd.strip().split()
        logger.info("Running %s with java %s", args, config["java"])
        result = subprocess.run(
            args=args,
            cwd="gradle",
            # env=patch_env({"JAVA_HOME": os.environ[f"JAVA_HOME_{config['java']}_X64"]}),
        )
        if result.returncode != 0:
            logger.error("Failed while running %s", args)
            return 1

    if result.returncode == 0:
        if not os.path.isdir("gradle"):
            logger.error("Cannot find gradle")
        elif not os.path.isdir("gradle/build"):
            logger.error("Cannot find gradle/build")
        elif not os.path.isdir("gradle/build/distributions"):
            logger.error("Cannot find gradle/build/distributions")

        logger.info(
            "Found the following files in gradle/build/distributions: %s",
            list(Path("gradle").rglob("build/distributions/*")),
        )

        logger.info(
            "Found the following bin.zip files: %s",
            list(Path("gradle").rglob("*-bin.zip")),
        )

        filename = os.path.basename(config["output"])
        shutil.copy2(
            os.path.join("gradle", config["output"]),
            os.path.join("distributions", filename),
        )
        logger.info("Copied %s", filename)
        return 0
    else:
        logger.error("Cannot build %s", version)
        return 1


def main():
    arg_parser = argparse.ArgumentParser(sys.argv[0])
    arg_parser.add_argument(
        *("-v", "--verbose"),
        help="Enable verbose logging",
        action="store_true",
        default=False,
    )
    args = arg_parser.parse_args()

    configure_logging(args.verbose)

    os.makedirs("distributions", exist_ok=True)

    if not os.path.isdir("gradle"):
        result = subprocess.run(
            args=[
                *("git", "clone", "--quiet"),
                "--filter=blob:none",
                "https://github.com/gradle/gradle",
            ],
        )
        if result.returncode != 0:
            logger.error("Cannot clone the gradle repository.")
    else:
        logger.info("The gradle repository has been cloned already.")

    return build("v6.1.0")


if __name__ == "__main__":
    raise SystemExit(main())

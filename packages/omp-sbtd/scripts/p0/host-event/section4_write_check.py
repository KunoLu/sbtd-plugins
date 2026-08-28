"""Cloud §4 write-check: only the Host project dir, not kit templates."""


def is_unexpected_host_project_write(rel: str) -> bool:
    """True when a file sits under host-run/<runId>/project/ except config.yml.

    Kit paths like .../templates/project/gitignore.template are not Host writes.
    """
    parts = rel.split("/")
    if len(parts) < 3 or parts[0] != "host-run" or parts[2] != "project":
        return False
    return "/".join(parts[3:]) != ".omp/config.yml"

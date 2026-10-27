
#!/usr/bin/env python3
"""Update last-commit dates in configured Markdown tables."""

import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

README = Path("README.md")
CONFIG = Path("scripts/commit_dates.json")

GITHUB_REPOSITORY_URL = re.compile(
    r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)"
)
PLAIN_REPOSITORY = re.compile(
    r"(?<![\w.-])([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)(?![\w.-])"
)
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def split_table_row(line):
    """Split a Markdown table row into cells."""
    content = line.rstrip("\r\n").strip()
    if not content.startswith("|"):
        return None

    cells = content.strip("|").split("|")
    return [cell.strip() for cell in cells]


def is_table_separator(line):
    cells = split_table_row(line)
    return bool(cells) and all(
        re.fullmatch(r":?-{3,}:?", cell.replace(" ", ""))
        for cell in cells
    )


def get_heading(line):
    match = HEADING.match(line.rstrip("\r\n"))
    if not match:
        return None

    level = len(match.group(1))
    title = match.group(2).strip().replace("`", "")
    return level, title


def find_section(lines, section_name):
    """Return the line range belonging to a Markdown section."""
    target = None

    for index, line in enumerate(lines):
        heading = get_heading(line)
        if heading and heading[1] == section_name:
            if target is not None:
                raise RuntimeError(
                    f"Duplicate section heading: {section_name}"
                )
            target = (index, heading[0])

    if target is None:
        raise RuntimeError(f"Section not found: {section_name}")

    start, level = target
    end = len(lines)

    for index in range(start + 1, len(lines)):
        heading = get_heading(lines[index])
        if heading and heading[0] <= level:
            end = index
            break

    return start + 1, end


def find_table_header(lines, start, end, repository_column, date_column):
    """Find the configured table header and its column indexes."""
    matches = []

    for index in range(start, end - 1):
        cells = split_table_row(lines[index])
        if not cells or not is_table_separator(lines[index + 1]):
            continue

        if (
            repository_column in cells
            and date_column in cells
        ):
            matches.append((index, cells))

    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one table with columns "
            f"{repository_column!r} and {date_column!r}; "
            f"found {len(matches)}"
        )

    return matches[0]


def extract_repository(cell):
    """Extract owner/repo from a GitHub link or plain repository text."""
    match = GITHUB_REPOSITORY_URL.search(cell)

    if match:
        return match.group(1), match.group(2).removesuffix(".git")

    # Remove Markdown link labels and inline code delimiters.
    plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cell)
    plain = plain.replace("`", "")

    match = PLAIN_REPOSITORY.search(plain)
    if match:
        owner, repo = match.groups()
        if "." not in repo or repo.lower() == "git":
            return owner, repo

    return None


def get_last_commit_date(repository):
    """Get the latest commit date on the repository's default branch."""
    url = (
        f"https://api.github.com/repos/{repository}/commits"
        "?per_page=1"
    )
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "awesome-std-backports-date-updater",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        commits = json.load(response)

    if not commits:
        raise RuntimeError(f"No commits found: {repository}")

    commit = commits[0]["commit"]
    timestamp = (
        (commit.get("committer") or {}).get("date")
        or (commit.get("author") or {}).get("date")
    )

    if not timestamp:
        raise RuntimeError(f"Commit date unavailable: {repository}")

    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d")


def replace_cell(line, column_index, new_value):
    """Replace one cell while preserving the rest of the table row."""
    newline = ""
    if line.endswith("\r\n"):
        newline = "\r\n"
    elif line.endswith("\n"):
        newline = "\n"
    elif line.endswith("\r"):
        newline = "\r"

    content = line[:-len(newline)] if newline else line
    pipe_positions = [
        index for index, char in enumerate(content) if char == "|"
    ]

    if content.lstrip().startswith("|"):
        # Standard Markdown table with a leading pipe.
        start = pipe_positions[column_index] + 1
        end = pipe_positions[column_index + 1]
    else:
        start = pipe_positions[column_index] + 1
        end = pipe_positions[column_index + 1]

    old_cell = content[start:end]
    leading = old_cell[:len(old_cell) - len(old_cell.lstrip())]
    trailing = old_cell[len(old_cell.rstrip()):]

    return (
        content[:start]
        + leading
        + new_value
        + trailing
        + content[end:]
        + newline
    )


def main():
    with CONFIG.open("r", encoding="utf-8") as file:
        config = json.load(file)

    if not isinstance(config.get("tables"), list) or not config["tables"]:
        raise RuntimeError("Config must contain a non-empty 'tables' list")

    # Preserve the original line endings when possible.
    original_bytes = README.read_bytes()
    original = original_bytes.decode("utf-8")
    lines = original.splitlines(keepends=True)

    # Fetch and validate everything before writing README.
    updates = {}
    seen_sections = set()

    for table_config in config["tables"]:
        section = table_config["section"]
        repository_column = table_config["repository_column"]
        date_column = table_config["date_column"]
        excluded = {
            item.lower()
            for item in table_config.get("exclude_repositories", [])
        }

        if section in seen_sections:
            raise RuntimeError(f"Duplicate config section: {section}")
        seen_sections.add(section)

        start, end = find_section(lines, section)
        header_index, headers = find_table_header(
            lines,
            start,
            end,
            repository_column,
            date_column,
        )
        repository_index = headers.index(repository_column)
        date_index = headers.index(date_column)

        row_count = 0

        for index in range(header_index + 2, end):
            if not lines[index].lstrip().startswith("|"):
                break

            cells = split_table_row(lines[index])
            if not cells or all(not cell for cell in cells):
                continue

            if len(cells) != len(headers):
                raise RuntimeError(
                    f"Malformed table row in section {section}, "
                    f"line {index + 1}"
                )

            repository_parts = extract_repository(
                cells[repository_index]
            )
            if repository_parts is None:
                continue

            owner, repo = repository_parts
            repository = f"{owner}/{repo}"
            row_count += 1

            if repository.lower() in excluded:
                print(f"Excluded: {repository}")
                continue

            date = get_last_commit_date(repository)
            updates[index] = (date_index, date)
            print(f"{repository}: {date}")

        if row_count == 0:
            raise RuntimeError(
                f"No GitHub repositories found in section {section}"
            )

    for index, (column_index, date) in updates.items():
        lines[index] = replace_cell(
            lines[index], column_index, date
        )

    updated = "".join(lines)
    updated_bytes = updated.encode("utf-8")

    if updated_bytes != original_bytes:
        README.write_bytes(updated_bytes)
        print("README.md updated.")
    else:
        print("All commit dates are already up to date.")


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        KeyError,
        ValueError,
        RuntimeError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)

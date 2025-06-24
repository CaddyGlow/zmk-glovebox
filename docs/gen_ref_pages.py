"""Generate the code reference pages and navigation."""

from pathlib import Path

import mkdocs_gen_files


nav = mkdocs_gen_files.Nav()


def check_for_readme(module_dir: Path) -> str | None:
    """Check if a module directory has a README.md file and return its content."""
    readme_path = module_dir / "README.md"
    if readme_path.exists():
        return readme_path.read_text(encoding="utf-8")
    return None


for path in sorted(Path("glovebox").rglob("*.py")):
    module_path = path.relative_to(".").with_suffix("")
    doc_path = path.relative_to(".").with_suffix(".md")
    full_doc_path = Path("reference", doc_path)

    parts = tuple(module_path.parts)

    if parts[-1] == "__init__":
        parts = parts[:-1]
        doc_path = doc_path.with_name("index.md")
        full_doc_path = full_doc_path.with_name("index.md")
    elif parts[-1] == "__main__":
        continue

    nav[parts] = doc_path.as_posix()

    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        ident = ".".join(parts)
        fd.write(f"---\ntitle: {parts[-1]}\n---\n\n")

        # Check for README.md in the module directory (for __init__ files)
        if parts[-1] != parts[0] and path.name == "__init__.py":
            module_dir = path.parent
            readme_content = check_for_readme(module_dir)
            if readme_content:
                fd.write("## Module Overview\n\n")
                fd.write(readme_content)
                fd.write("\n\n## API Reference\n\n")

        fd.write(f"::: {ident}")

    mkdocs_gen_files.set_edit_path(full_doc_path, path)

with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())

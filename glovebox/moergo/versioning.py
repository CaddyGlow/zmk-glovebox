"""Layout versioning using parent_uuid relationships in MoErgo API."""

from datetime import datetime
from typing import Any

from ..cli.helpers.theme import Icons
from .client import MoErgoClient
from .client.models import MoErgoLayout


class LayoutVersion:
    """Represents a single version in a layout's lineage."""

    def __init__(self, layout_meta: dict[str, Any]):
        self.uuid = layout_meta["uuid"]
        self.parent_uuid = layout_meta.get("parent_uuid")
        self.title = layout_meta["title"]
        self.creator = layout_meta["creator"]
        self.date = layout_meta["date"]
        self.notes = layout_meta.get("notes", "")
        self.tags = layout_meta.get("tags", [])
        self.firmware_api_version = layout_meta["firmware_api_version"]
        self.children: list[LayoutVersion] = []

    @property
    def created_datetime(self) -> datetime:
        """Convert timestamp to datetime."""
        return datetime.fromtimestamp(self.date)

    @property
    def is_root(self) -> bool:
        """Check if this is a root version (no parent)."""
        return self.parent_uuid is None

    def add_child(self, child: "LayoutVersion") -> None:
        """Add a child version."""
        self.children.append(child)

    def __repr__(self) -> str:
        return f"LayoutVersion(uuid={self.uuid[:8]}..., title='{self.title}')"


class LayoutVersionTree:
    """Manages version relationships for layouts using parent_uuid."""

    def __init__(self, client: MoErgoClient):
        self.client = client
        self._version_cache: dict[str, LayoutVersion] = {}

    async def get_version_tree(self, layout_uuid: str) -> LayoutVersion:
        """Get the complete version tree for a layout, starting from root."""
        # First, find the root of this layout's lineage
        root_uuid = await self._find_root_version(layout_uuid)

        # Build the complete tree from root
        root_version = await self._build_tree_from_root(root_uuid)

        return root_version

    async def _find_root_version(self, layout_uuid: str) -> str:
        """Find the root version by following parent_uuid links."""
        current_uuid = layout_uuid
        visited: set[str] = set()

        while current_uuid and current_uuid not in visited:
            visited.add(current_uuid)

            try:
                meta_response = self.client.get_layout_meta(current_uuid)
                layout_meta = meta_response.get("layout_meta", meta_response)
                parent_uuid = layout_meta.get("parent_uuid")

                if not parent_uuid:
                    # Found root
                    return current_uuid

                current_uuid = parent_uuid

            except Exception:
                # If we can't fetch a parent, current is the root we can access
                break

        return current_uuid

    async def _build_tree_from_root(self, root_uuid: str) -> LayoutVersion:
        """Build complete version tree starting from root."""
        # Get all user layouts to find children relationships
        all_layouts = self.client.list_user_layouts()

        # Create a map of parent_uuid -> children
        children_map: dict[str, list[dict[str, Any]]] = {}
        all_metas = {}

        # Fetch metadata for all layouts and build parent-child map
        for layout_info in all_layouts:
            try:
                meta_response = self.client.get_layout_meta(layout_info["uuid"])
                layout_meta = meta_response.get("layout_meta", meta_response)
                all_metas[layout_info["uuid"]] = layout_meta

                parent_uuid = layout_meta.get("parent_uuid")
                if parent_uuid:
                    if parent_uuid not in children_map:
                        children_map[parent_uuid] = []
                    children_map[parent_uuid].append(layout_meta)

            except Exception:
                continue

        # Build the tree recursively
        def build_node(uuid: str) -> LayoutVersion:
            if uuid in self._version_cache:
                return self._version_cache[uuid]

            # Get metadata
            layout_meta = all_metas.get(uuid)
            if not layout_meta:
                # Try to fetch if not in our cache
                try:
                    meta_response = self.client.get_layout_meta(uuid)
                    layout_meta = meta_response.get("layout_meta", meta_response)
                except Exception as err:
                    raise ValueError(
                        f"Cannot fetch metadata for layout {uuid}"
                    ) from err

            # Create version node
            version = LayoutVersion(layout_meta)
            self._version_cache[uuid] = version

            # Add children recursively
            if uuid in children_map:
                for child_meta in children_map[uuid]:
                    child_version = build_node(child_meta["uuid"])
                    version.add_child(child_version)

            return version

        return build_node(root_uuid)

    def get_version_lineage(self, layout_uuid: str) -> list[LayoutVersion]:
        """Get the linear lineage from root to specified version."""
        # This is a simplified synchronous version for immediate use
        lineage: list[LayoutVersion] = []
        current_uuid = layout_uuid
        visited: set[str] = set()

        # Build lineage by following parent links backwards
        path_to_root = []
        while current_uuid and current_uuid not in visited:
            visited.add(current_uuid)

            try:
                meta_response = self.client.get_layout_meta(current_uuid)
                layout_meta = meta_response.get("layout_meta", meta_response)
                version = LayoutVersion(layout_meta)
                path_to_root.append(version)

                current_uuid = layout_meta.get("parent_uuid")

            except Exception:
                break

        # Reverse to get root-to-current order
        return list(reversed(path_to_root))

    def get_all_versions_in_family(self, layout_uuid: str) -> list[LayoutVersion]:
        """Get all versions in the same family tree."""
        try:
            # Find root
            lineage = self.get_version_lineage(layout_uuid)
            if not lineage:
                return []

            root_uuid = lineage[0].uuid

            # Get all layouts and find family members
            all_layouts = self.client.list_user_layouts()
            family_members = []

            for layout_info in all_layouts:
                try:
                    # Check if this layout belongs to our family
                    member_lineage = self.get_version_lineage(layout_info["uuid"])
                    if member_lineage and member_lineage[0].uuid == root_uuid:
                        # Same family
                        meta_response = self.client.get_layout_meta(layout_info["uuid"])
                        layout_meta = meta_response.get("layout_meta", meta_response)
                        family_members.append(LayoutVersion(layout_meta))

                except Exception:
                    continue

            # Sort by creation date
            family_members.sort(key=lambda v: v.date)
            return family_members

        except Exception:
            return []

    def create_new_version(
        self,
        parent_layout: MoErgoLayout,
        new_title: str,
        notes: str = "",
        tags: list[str] | None = None,
    ) -> str:
        """Create a new version of a layout with parent_uuid link."""
        import uuid

        new_uuid = str(uuid.uuid4())

        # Create new layout metadata with parent reference
        new_meta = {
            "uuid": new_uuid,
            "title": new_title,
            "notes": notes,
            "tags": tags or parent_layout.layout_meta.tags,
            "parent_uuid": parent_layout.layout_meta.uuid,  # Key: set parent reference
            "creator": parent_layout.layout_meta.creator,
            "firmware_api_version": parent_layout.layout_meta.firmware_api_version,
            "date": int(datetime.now().timestamp()),
            "unlisted": parent_layout.layout_meta.unlisted,
            "deleted": False,
            "compiled": False,
            "searchable": True,
        }

        # Create complete layout with parent's config as base
        complete_layout = {
            "layout_meta": new_meta,
            "config": parent_layout.config.model_dump(mode="json", by_alias=True),
        }

        # Upload the new version
        self.client.save_layout(new_uuid, complete_layout)

        return new_uuid

    def print_version_tree(self, root_version: LayoutVersion, indent: int = 0) -> None:
        """Print a visual representation of the version tree."""
        prefix = "  " * indent

        if indent == 0:
            folder_icon = Icons.get_icon("FOLDER", "text")
            print(f"{prefix}{folder_icon} {root_version.title}")
        else:
            print(
                f"{prefix}├─ v{root_version.created_datetime.strftime('%Y%m%d')} {root_version.title}"
            )

        link_icon = Icons.get_icon("LINK", "text")
        user_icon = Icons.get_icon("USER", "text")
        calendar_icon = Icons.get_icon("CALENDAR", "text")
        print(f"{prefix}   {link_icon} UUID: {root_version.uuid}")
        print(f"{prefix}   {user_icon} Creator: {root_version.creator}")
        print(f"{prefix}   {calendar_icon} Created: {root_version.created_datetime}")

        if root_version.notes:
            document_icon = Icons.get_icon("DOCUMENT", "text")
            print(f"{prefix}   {document_icon} Notes: {root_version.notes}")

        if root_version.tags:
            tag_icon = Icons.get_icon("TAG", "text")
            print(f"{prefix}   {tag_icon} Tags: {', '.join(root_version.tags)}")

        print()

        # Print children
        for child in root_version.children:
            self.print_version_tree(child, indent + 1)

    def print_version_lineage(self, lineage: list[LayoutVersion]) -> None:
        """Print a linear version lineage."""
        scroll_icon = Icons.get_icon("SCROLL", "text")
        print(f"{scroll_icon} Version Lineage:")
        print("=" * 50)

        for i, version in enumerate(lineage):
            is_last = i == len(lineage) - 1
            connector = "└─" if is_last else "├─"

            print(f"{connector} v{i + 1}: {version.title}")
            link_icon = Icons.get_icon("LINK", "text")
            calendar_icon = Icons.get_icon("CALENDAR", "text")
            print(f"   {link_icon} UUID: {version.uuid}")
            print(f"   {calendar_icon} Created: {version.created_datetime}")

            if version.notes:
                # Truncate notes to first 160 characters
                truncated_notes = version.notes[:160]
                if len(version.notes) > 160:
                    truncated_notes += "..."
                document_icon = Icons.get_icon("DOCUMENT", "text")
                print(f"   {document_icon} Notes: {truncated_notes}")

            if not is_last:
                print("   │")


def create_layout_versioning(client: MoErgoClient) -> LayoutVersionTree:
    """Factory function to create layout versioning system."""
    return LayoutVersionTree(client)

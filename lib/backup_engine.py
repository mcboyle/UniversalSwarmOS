#!/usr/bin/env python3
"""
Automated Fleet Backup Engine (lib/backup_engine.py)

Enforces safety invariants for fleet script modification:
- Atomic, timestamped .tar.gz archive generation
- Cryptographic SHA-256 manifest generation
- Archive integrity self-verification
- Clean atomic restore preserving original permissions (0755/0775)
- Pre-modification gate support
"""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import sys
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_FLEET_TARGETS = [
    "bd-say.sh",
    "bd-status.sh",
    "bd-relay.sh",
    "bd-assign-lens.sh",
    "bd-launch-role.sh",
    "bd-persist/harness/bd-say.sh",
    "bd-persist/harness/bd-status.sh",
    "bd-persist/harness/bd-relay.sh",
    "bd-persist/harness/bd-assign-lens.sh",
    "bd-persist/harness/bd-launch-role.sh",
]


class BackupError(Exception):
    """Base exception for fleet backup engine errors."""


class BackupVerificationError(BackupError):
    """Raised when archive self-verification fails."""


class TargetNotFoundError(BackupError):
    """Raised when no valid targets can be found for backup."""


@dataclass
class FileEntry:
    path: str              # Original absolute or relative path
    rel_path: str          # Path inside archive
    sha256: str            # Hex SHA-256 digest
    mode: int              # Octal permission bits (e.g. 0o755)
    size: int              # Size in bytes
    mtime: float           # Last modification time


class BackupManifest:
    """Represents a cryptographic backup manifest."""

    def __init__(
        self,
        timestamp: str,
        archive_name: str,
        target_root: str,
        entries: dict[str, FileEntry] | None = None,
    ) -> None:
        self.timestamp = timestamp
        self.archive_name = archive_name
        self.target_root = target_root
        self.entries: dict[str, FileEntry] = entries or {}

    def add_entry(self, entry: FileEntry) -> None:
        self.entries[entry.rel_path] = entry

    def to_text(self) -> str:
        """Render manifest in standard TSV/header format."""
        lines = [
            f"# FLEET BACKUP MANIFEST: {self.timestamp}",
            f"# ARCHIVE: {self.archive_name}",
            f"# TARGET_ROOT: {self.target_root}",
            f"# SHA256{' ' * 58}MODE   SIZE        REL_PATH{' ' * 16}ORIGINAL_PATH",
        ]
        for rel_path in sorted(self.entries.keys()):
            entry = self.entries[rel_path]
            mode_str = oct(stat.S_IMODE(entry.mode))[2:].zfill(4)
            lines.append(
                f"{entry.sha256} {mode_str} {entry.size:<11} {entry.rel_path:<24} {entry.path}"
            )
        return "\n".join(lines) + "\n"

    @classmethod
    def from_text(cls, text: str) -> BackupManifest:
        """Parse manifest from text representation."""
        timestamp = ""
        archive_name = ""
        target_root = ""
        entries: dict[str, FileEntry] = {}

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("# FLEET BACKUP MANIFEST:"):
                timestamp = line.split(":", 1)[1].strip()
            elif line.startswith("# ARCHIVE:"):
                archive_name = line.split(":", 1)[1].strip()
            elif line.startswith("# TARGET_ROOT:"):
                target_root = line.split(":", 1)[1].strip()
            elif line.startswith("#"):
                continue
            else:
                parts = line.split(maxsplit=4)
                if len(parts) >= 4:
                    sha256_val = parts[0]
                    mode_val = int(parts[1], 8)
                    size_val = int(parts[2])
                    rel_path = parts[3]
                    orig_path = parts[4] if len(parts) > 4 else rel_path
                    entries[rel_path] = FileEntry(
                        path=orig_path,
                        rel_path=rel_path,
                        sha256=sha256_val,
                        mode=mode_val,
                        size=size_val,
                        mtime=0.0,
                    )
        return cls(
            timestamp=timestamp,
            archive_name=archive_name,
            target_root=target_root,
            entries=entries,
        )


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 digest of a file on disk."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_stream_sha256(stream) -> tuple[str, int]:
    """Compute SHA-256 digest and byte size of a readable binary stream."""
    hasher = hashlib.sha256()
    size = 0
    while chunk := stream.read(65536):
        hasher.update(chunk)
        size += len(chunk)
    return hasher.hexdigest(), size


class BackupEngine:
    """Core engine for creating, self-verifying, and restoring fleet backups."""

    def __init__(
        self,
        backup_dir: str | Path = "/home/mboyle/bd-persist/backups",
        target_root: str | Path = "/home/mboyle",
    ) -> None:
        self.backup_dir = Path(backup_dir)
        self.target_root = Path(target_root)

    def discover_targets(self, specified_targets: list[str] | None = None) -> list[tuple[Path, str]]:
        """
        Discover target files to back up.
        Returns list of tuples: (absolute_file_path, rel_path_inside_archive).
        """
        discovered: list[tuple[Path, str]] = []

        if specified_targets:
            for item in specified_targets:
                item_str = str(item).strip()
                if not item_str:
                    continue
                p = Path(item_str)
                if not p.is_absolute():
                    if ".." in p.parts:
                        raise BackupError(f"Path traversal detected in target: {item_str}")
                    full_p = (self.target_root / p).resolve()
                    if not full_p.is_relative_to(self.target_root.resolve()):
                        raise BackupError(f"Target path escapes target root: {item_str}")
                    try:
                        rel_p = str(full_p.relative_to(self.target_root.resolve()))
                    except ValueError:
                        raise BackupError(f"Target path escapes target root: {item_str}")
                else:
                    full_p = p.resolve()
                    try:
                        rel_p = str(full_p.relative_to(self.target_root.resolve()))
                    except ValueError:
                        # Outside target_root; use normalized path without leading slash
                        rel_p = str(full_p).lstrip("/")

                if ".." in Path(rel_p).parts:
                    raise BackupError(f"Path traversal detected in target: {item_str}")

                if not full_p.exists():
                    raise FileNotFoundError(f"Specified target does not exist: {full_p}")
                if not full_p.is_file():
                    raise BackupError(f"Specified target is not a regular file: {full_p}")
                discovered.append((full_p, rel_p))
        else:
            # Automatic discovery of default fleet targets under target_root
            for rel in DEFAULT_FLEET_TARGETS:
                full_p = (self.target_root / rel).resolve()
                if full_p.exists() and full_p.is_file():
                    discovered.append((full_p, rel))

        if not discovered:
            raise TargetNotFoundError(
                f"No target fleet scripts found to back up under '{self.target_root}'."
            )

        return discovered

    def create_backup(
        self,
        targets: list[str] | None = None,
        dest_dir: str | Path | None = None,
        manifest_path: str | Path | None = None,
    ) -> tuple[Path, Path]:
        """
        Atomically create a timestamped .tar.gz archive and manifest, then self-verify.

        Returns (archive_path, manifest_path).
        Raises BackupError if destination unwritable or verification fails.
        """
        out_dir = Path(dest_dir) if dest_dir else self.backup_dir

        # Ensure destination directory exists and is writable
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            # Probe writability
            test_file = out_dir / f".write_test_{os.getpid()}_{datetime.now(timezone.utc).timestamp()}"
            test_file.touch()
            test_file.unlink()
        except (PermissionError, OSError) as e:
            raise BackupError(f"Backup destination '{out_dir}' is not writable: {e}") from e

        # Discover targets
        target_files = self.discover_targets(targets)

        # Generate UTC timestamp e.g. 20260921T034500Z
        now_utc = datetime.now(timezone.utc)
        ts_slug = now_utc.strftime("%Y%m%dT%H%M%SZ")
        archive_name = f"fleet-backup-{ts_slug}.tar.gz"
        final_archive_path = out_dir / archive_name
        tmp_archive_path = out_dir / f"{archive_name}.tmp_{os.getpid()}"

        if manifest_path:
            final_manifest_path = Path(manifest_path)
        else:
            final_manifest_path = out_dir / f"fleet-backup-{ts_slug}.manifest"

        # Build manifest
        manifest = BackupManifest(
            timestamp=now_utc.isoformat(),
            archive_name=archive_name,
            target_root=str(self.target_root),
        )

        for full_p, rel_p in target_files:
            st = full_p.stat()
            file_sha = compute_sha256(full_p)
            entry = FileEntry(
                path=str(full_p),
                rel_path=rel_p,
                sha256=file_sha,
                mode=stat.S_IMODE(st.st_mode),
                size=st.st_size,
                mtime=st.st_mtime,
            )
            manifest.add_entry(entry)

        manifest_content = manifest.to_text()

        # Atomic tar.gz generation
        try:
            with tarfile.open(tmp_archive_path, "w:gz") as tar:
                # Add manifest into the archive
                import io
                manifest_bytes = manifest_content.encode("utf-8")
                tarinfo = tarfile.TarInfo(name="manifest.sha256")
                tarinfo.size = len(manifest_bytes)
                tarinfo.mtime = int(now_utc.timestamp())
                tarinfo.mode = 0o644
                tar.addfile(tarinfo, fileobj=io.BytesIO(manifest_bytes))

                # Add each target file
                for full_p, rel_p in target_files:
                    tar.add(str(full_p), arcname=rel_p, recursive=False)

            # Atomically move temporary archive to final destination
            tmp_archive_path.replace(final_archive_path)

            # Write external manifest file alongside archive
            final_manifest_path.write_text(manifest_content, encoding="utf-8")

        except Exception as e:
            if tmp_archive_path.exists():
                try:
                    tmp_archive_path.unlink()
                except OSError:
                    pass
            if final_archive_path.exists():
                try:
                    final_archive_path.unlink()
                except OSError:
                    pass
            raise BackupError(f"Failed to create backup archive: {e}") from e

        # Self-verify archive integrity immediately
        try:
            self.verify_backup(final_archive_path, final_manifest_path)
        except Exception as e:
            # Cleanup defective archive on verification failure
            if final_archive_path.exists():
                final_archive_path.unlink()
            if final_manifest_path.exists():
                final_manifest_path.unlink()
            raise BackupVerificationError(
                f"Post-creation archive self-verification failed: {e}"
            ) from e

        return final_archive_path, final_manifest_path

    def verify_backup(
        self,
        archive_path: Path,
        manifest_path: Path | None = None,
    ) -> bool:
        """
        Verify that archive is readable, uncorrupted, and matches manifest checksums.
        Raises BackupVerificationError if corrupt.
        """
        p = Path(archive_path)
        if not p.exists():
            raise BackupVerificationError(f"Archive file not found: {p}")
        if p.stat().st_size == 0:
            raise BackupVerificationError(f"Archive file is empty: {p}")

        # Obtain manifest content: either from external manifest or internal manifest.sha256
        manifest: BackupManifest | None = None
        if manifest_path and Path(manifest_path).exists():
            manifest = BackupManifest.from_text(Path(manifest_path).read_text(encoding="utf-8"))

        try:
            with tarfile.open(p, "r:gz") as tar:
                members = tar.getmembers()
                member_names = {m.name for m in members}

                # If manifest wasn't passed, load it from archive
                if manifest is None:
                    if "manifest.sha256" not in member_names:
                        raise BackupVerificationError(
                            "Archive does not contain internal 'manifest.sha256' and no external manifest provided."
                        )
                    manifest_f = tar.extractfile("manifest.sha256")
                    if manifest_f is None:
                        raise BackupVerificationError("Could not extract manifest from archive.")
                    manifest_text = manifest_f.read().decode("utf-8")
                    manifest = BackupManifest.from_text(manifest_text)

                # Verify each entry in manifest exists in tar and has matching sha256
                for rel_path, entry in manifest.entries.items():
                    if rel_path not in member_names:
                        raise BackupVerificationError(
                            f"Archive missing expected file listed in manifest: {rel_path}"
                        )
                    member = tar.getmember(rel_path)
                    f = tar.extractfile(member)
                    if f is None:
                        raise BackupVerificationError(f"Cannot read archived member: {rel_path}")
                    stream_sha, stream_size = compute_stream_sha256(f)
                    if stream_size != entry.size:
                        raise BackupVerificationError(
                            f"Size mismatch for {rel_path}: expected {entry.size}, got {stream_size}"
                        )
                    if stream_sha != entry.sha256:
                        raise BackupVerificationError(
                            f"Checksum mismatch for {rel_path}: expected {entry.sha256}, got {stream_sha}"
                        )
                    # Verify permissions
                    actual_mode = stat.S_IMODE(member.mode)
                    if actual_mode != entry.mode:
                        raise BackupVerificationError(
                            f"Permission mode mismatch for {rel_path}: expected {oct(entry.mode)}, got {oct(actual_mode)}"
                        )

        except tarfile.TarError as e:
            raise BackupVerificationError(f"Corrupted or invalid tar.gz archive '{p}': {e}") from e

        return True

    def restore_backup(
        self,
        archive_path: Path,
        target_root: str | Path | None = None,
        dry_run: bool = False,
    ) -> dict[str, str]:
        """
        Restore backed-up scripts cleanly and atomically from archive, preserving file modes.
        Returns dict mapping rel_path -> restored_file_path.
        """
        archive_p = Path(archive_path)
        dest_root = Path(target_root) if target_root else self.target_root

        # Self-verify archive before restoring
        self.verify_backup(archive_p)

        restored_files: dict[str, str] = {}

        with tarfile.open(archive_p, "r:gz") as tar:
            # Extract manifest
            manifest_f = tar.extractfile("manifest.sha256")
            if manifest_f is None:
                raise BackupError("Cannot read internal manifest from archive during restore.")
            manifest = BackupManifest.from_text(manifest_f.read().decode("utf-8"))

            dest_root_resolved = dest_root.resolve()
            for rel_path, entry in manifest.entries.items():
                target_dest = (dest_root / rel_path).resolve()
                if not target_dest.is_relative_to(dest_root_resolved):
                    raise BackupVerificationError(
                        f"Path traversal detected in archive member: {rel_path}"
                    )

                if dry_run:
                    restored_files[rel_path] = str(target_dest)
                    continue

                # Ensure destination directory exists
                target_dest.parent.mkdir(parents=True, exist_ok=True)

                member = tar.getmember(rel_path)
                member_file = tar.extractfile(member)
                if member_file is None:
                    raise BackupError(f"Failed to extract {rel_path} from archive.")

                # Atomic write via temporary file
                tmp_dest = target_dest.parent / f".{target_dest.name}.restore_tmp_{os.getpid()}"
                try:
                    with open(tmp_dest, "wb") as out_f:
                        while chunk := member_file.read(65536):
                            out_f.write(chunk)

                    # Preserve original mode (e.g. 0755/0775 executable bits)
                    os.chmod(tmp_dest, entry.mode)

                    # Verify restored file checksum on disk before renaming
                    disk_sha = compute_sha256(tmp_dest)
                    if disk_sha != entry.sha256:
                        raise BackupVerificationError(
                            f"Restored file checksum failed for {rel_path}: expected {entry.sha256}, got {disk_sha}"
                        )

                    # Atomic replace
                    tmp_dest.replace(target_dest)
                    restored_files[rel_path] = str(target_dest)

                finally:
                    if tmp_dest.exists():
                        try:
                            tmp_dest.unlink()
                        except OSError:
                            pass

        return restored_files


def main() -> int:
    """CLI entrypoint for backup engine."""
    parser = argparse.ArgumentParser(
        description="Automated Fleet Backup Engine & Safety Gate",
        prog="bd-backup",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: create
    create_parser = subparsers.add_parser("create", help="Create atomic backup archive")
    create_parser.add_argument(
        "--targets",
        nargs="*",
        help="Target fleet scripts to back up (comma or space-separated)",
    )
    create_parser.add_argument(
        "--dest",
        default="/home/mboyle/bd-persist/backups",
        help="Destination directory for backup archives",
    )
    create_parser.add_argument(
        "--target-root",
        default="/home/mboyle",
        help="Base root directory for resolving target files",
    )
    create_parser.add_argument(
        "--manifest",
        help="Optional explicit path to output manifest file",
    )

    # Subcommand: verify
    verify_parser = subparsers.add_parser("verify", help="Verify archive integrity against manifest")
    verify_parser.add_argument(
        "--archive",
        required=True,
        help="Path to .tar.gz backup archive",
    )
    verify_parser.add_argument(
        "--manifest",
        help="Path to companion manifest file (optional; internal manifest used if omitted)",
    )

    # Subcommand: restore
    restore_parser = subparsers.add_parser("restore", help="Restore scripts cleanly from backup archive")
    restore_parser.add_argument(
        "--archive",
        required=True,
        help="Path to .tar.gz backup archive",
    )
    restore_parser.add_argument(
        "--target-root",
        help="Destination root directory to restore files into (defaults to original paths)",
    )
    restore_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate restoration without writing files",
    )

    # Subcommand: list
    list_parser = subparsers.add_parser("list", help="List existing fleet backup archives")
    list_parser.add_argument(
        "--dest",
        default="/home/mboyle/bd-persist/backups",
        help="Backup directory to scan",
    )

    args = parser.parse_args()

    try:
        if args.command == "create":
            # Flatten targets if comma-separated strings were passed
            target_list: list[str] = []
            if args.targets:
                for item in args.targets:
                    for sub in item.split(","):
                        s = sub.strip()
                        if s:
                            target_list.append(s)

            engine = BackupEngine(backup_dir=args.dest, target_root=args.target_root)
            archive_path, _ = engine.create_backup(
                targets=target_list if target_list else None,
                dest_dir=args.dest,
                manifest_path=args.manifest,
            )
            # In accordance with interface contract: write archive path to stdout
            print(str(archive_path.resolve()))
            return 0

        elif args.command == "verify":
            engine = BackupEngine()
            archive_path = Path(args.archive)
            manifest_path: Path | None = Path(args.manifest) if args.manifest else None
            engine.verify_backup(archive_path, manifest_path)
            print(f"VERIFIED: {archive_path}")
            return 0

        elif args.command == "restore":
            engine = BackupEngine()
            archive_path = Path(args.archive)
            restored = engine.restore_backup(
                archive_path=archive_path,
                target_root=args.target_root,
                dry_run=args.dry_run,
            )
            print(f"RESTORED: {len(restored)} files from {archive_path}")
            for rel, full in restored.items():
                print(f"  {rel} -> {full}")
            return 0

        elif args.command == "list":
            dest_dir = Path(args.dest)
            if not dest_dir.exists():
                print(f"No backup directory found at {dest_dir}")
                return 0
            archives = sorted(dest_dir.glob("fleet-backup-*.tar.gz"))
            if not archives:
                print(f"No fleet backups found in {dest_dir}")
                return 0
            for a in archives:
                print(f"{a.name} ({a.stat().st_size} bytes)")
            return 0

    except (BackupError, OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

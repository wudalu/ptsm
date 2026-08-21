from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import errno
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Iterator
from uuid import uuid4


_SAFE_ARTIFACT_RUN_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,159}$")


@dataclass
class _WorkflowArtifactWriteTracker:
    """Per-invocation ownership records for newly-created direct artifacts.

    The tracker deliberately records *creation* only.  A workflow that merely
    merges into an older artifact did not gain authority to have that artifact
    scrubbed or published by this invocation.  Each entry is refreshed after a
    tracked store update so cleanup can pin the exact leaf and parent it saw.
    """

    owner: object
    base_identity_before_invoke: os.stat_result | None
    writes: dict[Path, "ArtifactFileIdentity"]


_ACTIVE_WORKFLOW_ARTIFACT_WRITES: ContextVar[_WorkflowArtifactWriteTracker | None] = ContextVar(
    "active_workflow_artifact_writes",
    default=None,
)


@dataclass(frozen=True)
class ArtifactFileIdentity:
    """The exact artifact leaf and directory used for a safe file operation."""

    file: os.stat_result
    parent: os.stat_result
    payload_sha256: str | None = None


class FileArtifactStore:
    """Persist final workflow artifacts to the local filesystem."""

    def __init__(self, base_dir: Path | str = "outputs/artifacts"):
        self.base_dir = Path(base_dir)

    def write(
        self,
        payload: dict[str, object],
        *,
        run_key: str | None = None,
        expected_base_identity: os.stat_result | None = None,
    ) -> Path:
        """Write a new artifact without allowing a caller to rebind its root.

        Normal callers may create the artifact root.  A guarded workflow passes
        the identity captured before untrusted execution; in that mode this
        method never creates or writes through a replacement directory.
        """
        if run_key is None:
            slug = str(uuid4())
        elif isinstance(run_key, str) and _SAFE_ARTIFACT_RUN_KEY.fullmatch(run_key):
            slug = run_key
        else:
            raise ValueError("artifact run_key must be a safe filename stem")
        tracker = self._active_workflow_tracker()
        if (
            expected_base_identity is None
            and tracker is not None
            and tracker.base_identity_before_invoke is not None
        ):
            # If the root existed before untrusted workflow execution, every
            # creation must stay in that exact directory.  This turns a root
            # rebind into a failed write rather than a cleanup target change.
            expected_base_identity = tracker.base_identity_before_invoke
        if expected_base_identity is None:
            self.base_dir.mkdir(parents=True, exist_ok=True)
        base_fd, base_identity = self._open_parent_directory(
            self.base_dir,
            expected_parent_identity=expected_base_identity,
        )
        try:
            suffix = 1
            while True:
                artifact_name = (
                    f"{slug}.json" if suffix == 1 else f"{slug}-{suffix}.json"
                )
                try:
                    artifact_identity = self._create_json(
                        artifact_name=artifact_name,
                        parent_fd=base_fd,
                        parent_path=self.base_dir,
                        parent_identity=base_identity,
                        payload=payload,
                    )
                except FileExistsError:
                    suffix += 1
                    continue
                artifact_path = self.base_dir / artifact_name
                self._track_new_workflow_write(
                    artifact_path,
                    ArtifactFileIdentity(
                        file=artifact_identity,
                        parent=base_identity,
                        payload_sha256=_payload_sha256(
                            json.dumps(
                                payload,
                                ensure_ascii=False,
                                indent=2,
                            ).encode("utf-8")
                        ),
                    ),
                )
                return artifact_path
        finally:
            os.close(base_fd)

    def read(self, path: Path | str) -> dict[str, object]:
        payload, _ = self.read_with_identity(path)
        return payload

    def read_with_identity(
        self,
        path: Path | str,
        *,
        expected_parent_identity: os.stat_result | None = None,
    ) -> tuple[dict[str, object], ArtifactFileIdentity]:
        """Read one regular JSON leaf without following it or its parent swap.

        The returned identity pins both the payload's file and the directory
        descriptor that resolved it.  Callers performing a read/replace
        transaction pass it to :meth:`replace` so a later parent-path rebind
        fails before any write is routed through that new directory.
        """
        artifact_path = Path(path)
        raw_payload, identity = self._read_bytes_without_following_leaf(
            artifact_path,
            expected_parent_identity=expected_parent_identity,
        )
        try:
            payload = json.loads(raw_payload.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise OSError(
                errno.EILSEQ,
                "artifact is not valid UTF-8",
                str(artifact_path),
            ) from exc
        if not isinstance(payload, dict):
            raise json.JSONDecodeError("artifact root must be an object", "", 0)
        return payload, ArtifactFileIdentity(
            file=identity.file,
            parent=identity.parent,
            payload_sha256=_payload_sha256(raw_payload),
        )

    def merge(self, path: Path | str, payload: dict[str, object]) -> Path:
        artifact_path = Path(path)
        current, identity = self.read_with_identity(artifact_path)
        current.update(payload)
        replacement_identity = self._replace_json(
            artifact_path,
            current,
            expected_identity=identity,
        )
        self._refresh_tracked_workflow_write(artifact_path, replacement_identity)
        return artifact_path

    @contextmanager
    def track_workflow_writes(self) -> Iterator[_WorkflowArtifactWriteTracker]:
        """Track newly-created direct artifacts for one workflow invocation.

        This is intentionally a ContextVar rather than a directory listing:
        parallel invocations and foreign settled artifacts remain outside this
        invocation's authority.  The root identity is captured before the
        workflow runs; when it exists, tracked creation and later cleanup must
        continue through that same directory inode.
        """
        tracker = _WorkflowArtifactWriteTracker(
            owner=self,
            base_identity_before_invoke=self._capture_base_identity(),
            writes={},
        )
        token = _ACTIVE_WORKFLOW_ARTIFACT_WRITES.set(tracker)
        try:
            yield tracker
        finally:
            _ACTIVE_WORKFLOW_ARTIFACT_WRITES.reset(token)

    def clear_untrusted_carousel_delivery(
        self,
        path: Path | str,
        *,
        tracker: _WorkflowArtifactWriteTracker,
    ) -> bool:
        """Clear only one tracked, direct workflow handoff.

        The caller gets this path from the active write tracker, never from a
        directory scan, so an exception in one run cannot revoke another run's
        settled receipt. Nested learning-series artifacts are not eligible.
        """
        artifact_path = Path(path)
        tracked_identity = self._tracked_workflow_identity(
            artifact_path,
            tracker=tracker,
        )
        if tracked_identity is None:
            raise ValueError("workflow artifact handoff is not owned by this invocation")
        payload, identity = self.read_with_identity(
            artifact_path,
            expected_parent_identity=tracked_identity.parent,
        )
        if not _same_artifact_identity(identity, tracked_identity):
            raise OSError(
                errno.ELOOP,
                "workflow artifact changed after tracked store write",
                str(artifact_path),
            )
        if "carousel_delivery" not in payload:
            return False
        payload.pop("carousel_delivery", None)
        replacement_identity = self._replace_json(
            artifact_path,
            payload,
            expected_identity=identity,
        )
        tracker.writes[self._workflow_path_key(artifact_path)] = replacement_identity
        return True

    def replace(
        self,
        path: Path | str,
        payload: dict[str, object],
        *,
        expected_identity: ArtifactFileIdentity | None = None,
        require_single_link: bool = False,
    ) -> Path:
        """Replace an owned artifact with a fully controlled JSON envelope."""
        artifact_path = Path(path)
        replacement_identity = self._replace_json(
            artifact_path,
            payload,
            expected_identity=expected_identity,
            require_single_link=require_single_link,
        )
        self._refresh_tracked_workflow_write(artifact_path, replacement_identity)
        return artifact_path

    def tracked_workflow_artifact_paths(
        self,
        tracker: _WorkflowArtifactWriteTracker | None,
    ) -> tuple[Path, ...]:
        """Return only direct artifacts newly created by this store/context."""
        if tracker is None or tracker.owner is not self:
            return ()
        return tuple(identity_path for identity_path in tracker.writes)

    def is_tracked_workflow_artifact(
        self,
        path: Path | str,
        *,
        tracker: _WorkflowArtifactWriteTracker | None,
    ) -> bool:
        """Whether this invocation created ``path`` through this store."""
        return self._tracked_workflow_identity(Path(path), tracker=tracker) is not None

    def tracked_workflow_artifact_is_current(
        self,
        path: Path | str,
        *,
        tracker: _WorkflowArtifactWriteTracker | None,
    ) -> bool:
        """Check the exact tracked leaf before an ordinary side effect."""
        artifact_path = Path(path)
        tracked_identity = self._tracked_workflow_identity(
            artifact_path,
            tracker=tracker,
        )
        if tracked_identity is None:
            return False
        try:
            _, current_identity = self.read_with_identity(
                artifact_path,
                expected_parent_identity=tracked_identity.parent,
            )
        except (OSError, json.JSONDecodeError):
            return False
        return _same_artifact_identity(current_identity, tracked_identity)

    def merge_tracked_workflow_artifact(
        self,
        path: Path | str,
        payload: dict[str, object],
        *,
        tracker: _WorkflowArtifactWriteTracker,
    ) -> Path:
        """Merge only into the exact artifact newly created by this run.

        This is the post-workflow counterpart to receipt scrubbing.  It pins
        the last tracked inode and payload before replacing it, so a later
        swap cannot resurrect a forged delivery through a metadata merge.
        """
        artifact_path = Path(path)
        tracked_identity = self._tracked_workflow_identity(
            artifact_path,
            tracker=tracker,
        )
        if tracked_identity is None:
            raise ValueError("workflow artifact is not owned by this invocation")
        current, current_identity = self.read_with_identity(
            artifact_path,
            expected_parent_identity=tracked_identity.parent,
        )
        if not _same_artifact_identity(current_identity, tracked_identity):
            raise OSError(
                errno.ELOOP,
                "workflow artifact changed after tracked store write",
                str(artifact_path),
            )
        current.update(payload)
        replacement_identity = self._replace_json(
            artifact_path,
            current,
            expected_identity=current_identity,
        )
        tracker.writes[self._workflow_path_key(artifact_path)] = replacement_identity
        return artifact_path

    def _active_workflow_tracker(self) -> _WorkflowArtifactWriteTracker | None:
        tracker = _ACTIVE_WORKFLOW_ARTIFACT_WRITES.get()
        return tracker if tracker is not None and tracker.owner is self else None

    @staticmethod
    def _workflow_path_key(artifact_path: Path) -> Path:
        # This is lexical normalization only.  Ownership is established by
        # captured directory/file identities, never by ``resolve()`` alone.
        return Path(os.path.abspath(os.path.normpath(os.fspath(artifact_path))))

    def _track_new_workflow_write(
        self,
        artifact_path: Path,
        identity: ArtifactFileIdentity,
    ) -> None:
        tracker = self._active_workflow_tracker()
        if tracker is None:
            return
        if (
            tracker.base_identity_before_invoke is not None
            and not os.path.samestat(
                identity.parent,
                tracker.base_identity_before_invoke,
            )
        ):
            return
        tracker.writes[self._workflow_path_key(artifact_path)] = identity

    def _refresh_tracked_workflow_write(
        self,
        artifact_path: Path,
        identity: ArtifactFileIdentity,
    ) -> None:
        tracker = self._active_workflow_tracker()
        if tracker is None:
            return
        key = self._workflow_path_key(artifact_path)
        if key not in tracker.writes:
            # An update of an older or foreign artifact does not grant this
            # run ownership.  It must never become a later scrub target.
            return
        previous = tracker.writes[key]
        if not os.path.samestat(identity.parent, previous.parent):
            raise OSError(
                errno.ELOOP,
                "tracked workflow artifact parent changed",
                str(artifact_path),
            )
        tracker.writes[key] = identity

    def _tracked_workflow_identity(
        self,
        artifact_path: Path,
        *,
        tracker: _WorkflowArtifactWriteTracker | None,
    ) -> ArtifactFileIdentity | None:
        if tracker is None or tracker.owner is not self:
            return None
        return tracker.writes.get(self._workflow_path_key(artifact_path))

    def _capture_base_identity(self) -> os.stat_result | None:
        try:
            base_fd, base_identity = self._open_parent_directory(self.base_dir)
        except FileNotFoundError:
            return None
        try:
            return base_identity
        finally:
            os.close(base_fd)

    def remove_entry(
        self,
        path: Path | str,
        *,
        expected_parent_identity: os.stat_result,
    ) -> None:
        """Refuse online cleanup of a mutable leaf.

        A same-UID writer can replace the leaf between an identity check and
        ``unlinkat``.  Rejected artifacts are therefore left for trusted,
        offline maintenance while runtime callers fail closed and never reuse
        or publish them.
        """
        del path, expected_parent_identity
        raise OSError(
            errno.EPERM,
            "automatic artifact removal requires trusted offline maintenance",
        )

    @classmethod
    def _create_json(
        cls,
        *,
        artifact_name: str,
        parent_fd: int,
        parent_path: Path,
        parent_identity: os.stat_result,
        payload: dict[str, object],
    ) -> os.stat_result:
        """Create a new artifact name atomically without a cleanup alias."""
        encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        artifact_fd = os.open(artifact_name, flags, 0o600, dir_fd=parent_fd)
        try:
            _write_all(artifact_fd, encoded)
            os.fsync(artifact_fd)
            artifact_identity = os.fstat(artifact_fd)
            cls._verify_created_artifact(
                artifact_name,
                parent_fd,
                artifact_identity,
            )
            cls._verify_opened_payload(
                artifact_fd,
                encoded,
                error_message="artifact creation payload changed",
                name=artifact_name,
            )
            os.fsync(parent_fd)
            cls._verify_created_artifact(
                artifact_name,
                parent_fd,
                artifact_identity,
            )
            cls._verify_opened_payload(
                artifact_fd,
                encoded,
                error_message="artifact creation payload changed",
                name=artifact_name,
            )
            cls._verify_parent_path_identity(parent_path, parent_identity)
            return artifact_identity
        finally:
            os.close(artifact_fd)

    def _replace_json(
        self,
        artifact_path: Path,
        payload: dict[str, object],
        *,
        expected_identity: ArtifactFileIdentity | None = None,
        expected_parent_identity: os.stat_result | None = None,
        require_single_link: bool = False,
    ) -> ArtifactFileIdentity:
        """Atomically replace one entry through the same verified directory fd.

        A path string can be rebound after a caller validates it.  All temp
        creation, lstat checks, and ``os.replace`` therefore use the
        one opened parent descriptor.  A post-operation path identity check
        reports a parent rebind instead of returning a now-misdirected path.
        """
        encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        temporary_name = f".{artifact_path.name}.{uuid4().hex}.tmp"
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        if expected_identity is not None:
            expected_parent_identity = expected_identity.parent
        parent_fd, parent_identity = self._open_parent_directory(
            artifact_path.parent,
            expected_parent_identity=expected_parent_identity,
        )
        temporary_fd: int | None = None
        try:
            temporary_fd = os.open(
                temporary_name,
                flags,
                0o600,
                dir_fd=parent_fd,
            )
            _write_all(temporary_fd, encoded)
            os.fsync(temporary_fd)
            temporary_identity = os.fstat(temporary_fd)
            self._verify_opened_payload(
                temporary_fd,
                encoded,
                error_message="artifact replacement payload changed",
                name=temporary_name,
            )
            self._verify_replace_target(
                artifact_path.name,
                parent_fd,
                expected_identity=expected_identity,
                require_single_link=require_single_link,
            )
            self._verify_temporary_source(
                temporary_name,
                parent_fd,
                temporary_identity,
            )
            try:
                os.replace(
                    temporary_name,
                    artifact_path.name,
                    src_dir_fd=parent_fd,
                    dst_dir_fd=parent_fd,
                )
            except (NotImplementedError, TypeError) as exc:
                raise OSError(
                    errno.ENOTSUP,
                    "atomic artifact replacement by directory descriptor is unsupported",
                    artifact_path.name,
                ) from exc
            self._verify_replaced_artifact(
                artifact_path.name,
                parent_fd,
                temporary_identity,
            )
            self._verify_opened_payload(
                temporary_fd,
                encoded,
                error_message="artifact replacement payload changed",
                name=artifact_path.name,
            )
            os.fsync(parent_fd)
            self._verify_replaced_artifact(
                artifact_path.name,
                parent_fd,
                temporary_identity,
            )
            self._verify_opened_payload(
                temporary_fd,
                encoded,
                error_message="artifact replacement payload changed",
                name=artifact_path.name,
            )
            self._verify_parent_path_identity(
                artifact_path.parent,
                parent_identity,
            )
            return ArtifactFileIdentity(
                file=temporary_identity,
                parent=parent_identity,
                payload_sha256=_payload_sha256(encoded),
            )
        finally:
            try:
                if temporary_fd is not None:
                    os.close(temporary_fd)
            finally:
                os.close(parent_fd)

    @staticmethod
    def _open_parent_directory(
        parent_path: Path,
        *,
        expected_parent_identity: os.stat_result | None = None,
    ) -> tuple[int, os.stat_result]:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        parent_fd = os.open(parent_path, flags)
        try:
            parent_identity = os.fstat(parent_fd)
            if not stat.S_ISDIR(parent_identity.st_mode):
                raise OSError(
                    errno.ENOTDIR,
                    "artifact parent is not a directory",
                    str(parent_path),
                )
            if (
                expected_parent_identity is not None
                and not os.path.samestat(parent_identity, expected_parent_identity)
            ):
                raise OSError(
                    errno.ELOOP,
                    "artifact parent changed",
                    str(parent_path),
                )
            return parent_fd, parent_identity
        except Exception:
            os.close(parent_fd)
            raise

    @staticmethod
    def _entry_lstat(entry_name: str, parent_fd: int) -> os.stat_result:
        return os.stat(entry_name, dir_fd=parent_fd, follow_symlinks=False)

    @staticmethod
    def _verify_parent_path_identity(
        parent_path: Path,
        parent_identity: os.stat_result,
    ) -> None:
        try:
            current_identity = parent_path.stat()
        except OSError as exc:
            raise OSError(
                errno.ELOOP,
                "artifact parent changed",
                str(parent_path),
            ) from exc
        if not os.path.samestat(current_identity, parent_identity):
            raise OSError(
                errno.ELOOP,
                "artifact parent changed",
                str(parent_path),
            )

    @classmethod
    def _verify_temporary_source(
        cls,
        temporary_name: str,
        parent_fd: int,
        temporary_identity: os.stat_result,
    ) -> None:
        """Reject a temporary entry rebound after its protected open."""
        current_identity = cls._entry_lstat(temporary_name, parent_fd)
        if (
            stat.S_ISLNK(current_identity.st_mode)
            or not stat.S_ISREG(current_identity.st_mode)
            or current_identity.st_nlink != 1
            or temporary_identity.st_nlink != 1
            or not os.path.samestat(current_identity, temporary_identity)
        ):
            raise OSError(
                errno.ELOOP,
                "artifact temporary source changed before replacement",
                temporary_name,
            )

    @classmethod
    def _verify_replaced_artifact(
        cls,
        artifact_name: str,
        parent_fd: int,
        temporary_identity: os.stat_result,
    ) -> None:
        """Fail closed if a source swap wins the final pre-replace race."""
        try:
            current_identity = cls._entry_lstat(artifact_name, parent_fd)
        except OSError:
            raise
        if (
            stat.S_ISREG(current_identity.st_mode)
            and not stat.S_ISLNK(current_identity.st_mode)
            and current_identity.st_nlink == 1
            and temporary_identity.st_nlink == 1
            and os.path.samestat(current_identity, temporary_identity)
        ):
            return
        raise OSError(
            errno.ELOOP,
            "artifact replacement source changed",
            artifact_name,
        )

    @classmethod
    def _verify_created_artifact(
        cls,
        artifact_name: str,
        parent_fd: int,
        artifact_identity: os.stat_result,
    ) -> None:
        current_identity = cls._entry_lstat(artifact_name, parent_fd)
        if (
            not stat.S_ISREG(current_identity.st_mode)
            or stat.S_ISLNK(current_identity.st_mode)
            or current_identity.st_nlink != 1
            or artifact_identity.st_nlink != 1
            or not os.path.samestat(current_identity, artifact_identity)
        ):
            raise OSError(
                errno.ELOOP,
                "artifact creation source changed",
                artifact_name,
            )

    @staticmethod
    def _verify_opened_payload(
        fd: int,
        expected_payload: bytes,
        *,
        error_message: str,
        name: str,
    ) -> None:
        """Verify the still-open inode was not mutated through a hidden peer."""
        os.lseek(fd, 0, os.SEEK_SET)
        if _read_all(fd) != expected_payload:
            raise OSError(errno.EILSEQ, error_message, name)

    @classmethod
    def _verify_replace_target(
        cls,
        artifact_name: str,
        parent_fd: int,
        *,
        expected_identity: ArtifactFileIdentity | None,
        require_single_link: bool,
    ) -> None:
        if expected_identity is None and not require_single_link:
            return
        current_identity = cls._entry_lstat(artifact_name, parent_fd)
        if (
            not stat.S_ISREG(current_identity.st_mode)
            or stat.S_ISLNK(current_identity.st_mode)
            or (
                expected_identity is not None
                and not os.path.samestat(current_identity, expected_identity.file)
            )
            or (require_single_link and current_identity.st_nlink != 1)
        ):
            raise OSError(
                errno.ELOOP,
                "artifact path changed or is not a private regular file",
                artifact_name,
            )
        if expected_identity is None or expected_identity.payload_sha256 is None:
            return
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        target_fd = os.open(artifact_name, flags, dir_fd=parent_fd)
        try:
            opened_identity = os.fstat(target_fd)
            if (
                not os.path.samestat(opened_identity, expected_identity.file)
                or _payload_sha256(_read_all(target_fd))
                != expected_identity.payload_sha256
            ):
                raise OSError(
                    errno.ELOOP,
                    "artifact replacement target changed",
                    artifact_name,
                )
        finally:
            os.close(target_fd)

    @classmethod
    def _read_bytes_without_following_leaf(
        cls,
        artifact_path: Path,
        *,
        expected_parent_identity: os.stat_result | None,
    ) -> tuple[bytes, ArtifactFileIdentity]:
        """Open a regular leaf through a stable parent directory descriptor."""
        parent_fd, parent_identity = cls._open_parent_directory(
            artifact_path.parent,
            expected_parent_identity=expected_parent_identity,
        )
        fd: int | None = None
        try:
            before_open = cls._entry_lstat(artifact_path.name, parent_fd)
            if (
                not stat.S_ISREG(before_open.st_mode)
                or stat.S_ISLNK(before_open.st_mode)
            ):
                raise OSError(
                    errno.ELOOP,
                    "artifact path must be a regular file",
                    str(artifact_path),
                )
            flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(artifact_path.name, flags, dir_fd=parent_fd)
            opened_identity = os.fstat(fd)
            after_open = cls._entry_lstat(artifact_path.name, parent_fd)
            if (
                not stat.S_ISREG(opened_identity.st_mode)
                or not stat.S_ISREG(after_open.st_mode)
                or stat.S_ISLNK(after_open.st_mode)
                or not os.path.samestat(before_open, opened_identity)
                or not os.path.samestat(opened_identity, after_open)
            ):
                raise OSError(
                    errno.ELOOP,
                    "artifact path changed or is not a regular file",
                    str(artifact_path),
                )
            payload = _read_all(fd)
            cls._verify_parent_path_identity(artifact_path.parent, parent_identity)
            return payload, ArtifactFileIdentity(
                file=opened_identity,
                parent=parent_identity,
                payload_sha256=_payload_sha256(payload),
            )
        finally:
            try:
                if fd is not None:
                    os.close(fd)
            finally:
                os.close(parent_fd)

def _read_all(fd: int) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = os.read(fd, 64 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _payload_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _same_artifact_identity(
    current: ArtifactFileIdentity,
    expected: ArtifactFileIdentity,
) -> bool:
    if not (
        os.path.samestat(current.file, expected.file)
        and os.path.samestat(current.parent, expected.parent)
    ):
        return False
    return (
        expected.payload_sha256 is None
        or current.payload_sha256 == expected.payload_sha256
    )


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError(errno.EIO, "could not write artifact")
        view = view[written:]

import os
import hashlib
import shutil
import platform
from pathlib import Path
from typing import Optional
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# --- App ---

app = FastAPI(title="FileVault - File Manager API")

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

STATIC_DIR.mkdir(exist_ok=True)

# --- Models ---

class DeleteRequest(BaseModel):
    paths: list[str]


class FileNode(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int
    modified: float
    extension: str


# --- Helpers ---

SKIP_DIRS = {
    "$Recycle.Bin",
    "System Volume Information",
    "__pycache__",
    ".git",
    "node_modules",
}


def human_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def file_hash(path: str, chunk_size: int = 65536) -> Optional[str]:
    """Fast partial MD5 hash."""
    try:
        h = hashlib.md5()
        fsize = os.path.getsize(path)

        with open(path, "rb") as f:
            h.update(f.read(chunk_size))

            if fsize > chunk_size * 2:
                f.seek(-chunk_size, 2)
                h.update(f.read(chunk_size))

        return h.hexdigest()

    except (PermissionError, OSError):
        return None


def safe_stat(path: str) -> Optional[os.stat_result]:
    try:
        return os.stat(path)
    except (PermissionError, OSError, FileNotFoundError):
        return None


def filter_dirs(dirs: list[str]) -> list[str]:
    return [
        d for d in dirs
        if not d.startswith(".") and d not in SKIP_DIRS
    ]


# OneDrive Files On-Demand attribute flags (Windows)
FILE_ATTRIBUTE_OFFLINE = 0x1000
FILE_ATTRIBUTE_PINNED = 0x80000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x400000


def get_cloud_status(stat: os.stat_result) -> Optional[str]:
    """OneDrive sync status for a file: cloud_only, always_available, or local."""
    attrs = getattr(stat, "st_file_attributes", None)

    if attrs is None:
        return None

    if attrs & FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS or attrs & FILE_ATTRIBUTE_OFFLINE:
        return "cloud_only"

    if attrs & FILE_ATTRIBUTE_PINNED:
        return "always_available"

    return "local"


# --- Routes ---

@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/roots")
def get_roots():
    """Return system root directories."""
    roots = []
    system = platform.system()

    if system == "Windows":
        import string

        onedrive = os.environ.get("OneDriveConsumer") or os.environ.get("OneDrive")
        if onedrive and os.path.isdir(onedrive):
            roots.append({"path": onedrive, "label": "OneDrive"})

        home = os.environ.get("USERPROFILE")
        if home:
            for name in ["Desktop", "Documents", "Downloads", "Pictures"]:
                p = os.path.join(home, name)
                if os.path.isdir(p):
                    roots.append({"path": p, "label": name})

        for drive in string.ascii_uppercase:
            p = f"{drive}:\\"
            if os.path.exists(p):
                roots.append({
                    "path": p,
                    "label": f"Drive {drive}:"
                })
    else:
        home = str(Path.home())
        roots = [
            {"path": home, "label": "Home"},
            {"path": "/tmp", "label": "/tmp"},
            {"path": "/", "label": "Root /"},
        ]

    return {"roots": roots}


@app.get("/api/browse")
def browse_directory(
    path: str = Query(..., description="Absolute path")
):
    """Browse directory contents."""

    if not os.path.isdir(path):
        raise HTTPException(
            status_code=404,
            detail="Directory not found"
        )

    try:
        items = os.scandir(path)
    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail="Permission denied"
        )

    entries = []
    total_size = 0

    for entry in items:
        stat = safe_stat(entry.path)

        if stat is None:
            continue

        is_dir = entry.is_dir(follow_symlinks=False)

        size = stat.st_size if not is_dir else 0
        total_size += size

        entries.append({
            "name": entry.name,
            "path": entry.path,
            "is_dir": is_dir,
            "size": size,
            "size_human": human_size(size),
            "modified": stat.st_mtime,
            "extension": (
                Path(entry.name).suffix.lower()
                if not is_dir else ""
            ),
            "cloud_status": get_cloud_status(stat) if not is_dir else None,
        })

    # Directories first, then alphabetical
    entries.sort(
        key=lambda x: (
            not x["is_dir"],
            x["name"].lower()
        )
    )

    current = Path(path)

    parent = (
        str(current.parent)
        if current != current.anchor
        else None
    )

    return {
        "path": path,
        "parent": parent,
        "item_count": len(entries),
        "total_size": total_size,
        "total_size_human": human_size(total_size),
        "entries": entries,
    }


@app.get("/api/search")
def search_files(
    path: str = Query(...),
    query: str = Query(..., min_length=1),
):
    """Recursive filename search."""

    if not os.path.isdir(path):
        raise HTTPException(
            status_code=404,
            detail="Directory not found"
        )

    q = query.lower()
    matches = []

    for root, dirs, files in os.walk(
        path,
        onerror=lambda e: None
    ):
        dirs[:] = filter_dirs(dirs)

        for fname in files:
            if q in fname.lower():
                fpath = os.path.join(root, fname)

                stat = safe_stat(fpath)

                if stat:
                    matches.append({
                        "name": fname,
                        "path": fpath,
                        "dir": root,
                        "size": stat.st_size,
                        "size_human": human_size(stat.st_size),
                        "modified": stat.st_mtime,
                        "extension": Path(fname).suffix.lower(),
                        "cloud_status": get_cloud_status(stat),
                    })

        # Prevent runaway searches
        if len(matches) >= 500:
            break

    return {
        "query": query,
        "count": len(matches),
        "results": matches,
    }


@app.get("/api/duplicates")
def find_duplicates(
    path: str = Query(...),
    min_size: int = Query(
        1024,
        description="Minimum size in bytes"
    ),
):
    """Find duplicate files."""

    if not os.path.isdir(path):
        raise HTTPException(
            status_code=404,
            detail="Directory not found"
        )

    size_map: dict[int, list[str]] = defaultdict(list)
    cloud_only_size = 0
    cloud_only_count = 0

    # Pass 1 - group by file size (skip cloud-only files, hashing them
    # would force OneDrive to download every one and can hang for minutes)
    for root, dirs, files in os.walk(
        path,
        onerror=lambda e: None
    ):
        dirs[:] = filter_dirs(dirs)

        for fname in files:
            fpath = os.path.join(root, fname)

            stat = safe_stat(fpath)

            if not stat or stat.st_size < min_size:
                continue

            if get_cloud_status(stat) == "cloud_only":
                cloud_only_count += 1
                cloud_only_size += stat.st_size
                continue

            size_map[stat.st_size].append(fpath)

    # Pass 2 - hash matching-size files
    hash_map: dict[str, list[str]] = defaultdict(list)

    for _, paths in size_map.items():
        if len(paths) < 2:
            continue

        for p in paths:
            h = file_hash(p)

            if h:
                hash_map[h].append(p)

    # Build duplicate groups
    groups = []
    wasted = 0

    for h, paths in hash_map.items():
        if len(paths) < 2:
            continue

        stat = safe_stat(paths[0])
        fsize = stat.st_size if stat else 0

        wasted_here = fsize * (len(paths) - 1)
        wasted += wasted_here

        groups.append({
            "hash": h,
            "size": fsize,
            "size_human": human_size(fsize),
            "count": len(paths),
            "wasted_human": human_size(wasted_here),
            "files": [
                {
                    "path": p,
                    "name": os.path.basename(p),
                    "dir": os.path.dirname(p),
                    "cloud_status": get_cloud_status(st) if (st := safe_stat(p)) else None,
                }
                for p in paths
            ],
        })

    groups.sort(
        key=lambda x: x["size"] * (x["count"] - 1),
        reverse=True
    )

    return {
        "scan_path": path,
        "duplicate_groups": len(groups),
        "wasted_space": wasted,
        "wasted_space_human": human_size(wasted),
        "groups": groups,
        "cloud_skipped_count": cloud_only_count,
        "cloud_skipped_size_human": human_size(cloud_only_size),
    }


@app.delete("/api/delete")
def delete_items(req: DeleteRequest):
    """Delete files/directories."""

    results = []

    for p in req.paths:
        try:
            if os.path.isdir(p):
                shutil.rmtree(p)

                results.append({
                    "path": p,
                    "ok": True,
                    "type": "directory",
                })

            elif os.path.isfile(p):
                os.remove(p)

                results.append({
                    "path": p,
                    "ok": True,
                    "type": "file",
                })

            else:
                results.append({
                    "path": p,
                    "ok": False,
                    "error": "Not found",
                })

        except PermissionError:
            results.append({
                "path": p,
                "ok": False,
                "error": "Permission denied",
            })

        except Exception as e:
            results.append({
                "path": p,
                "ok": False,
                "error": str(e),
            })

    deleted = [r for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]

    return {
        "deleted": len(deleted),
        "failed": len(failed),
        "results": results,
    }


# --- Static Files ---

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static"
)

# --- Main ---

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,  # safer on Windows + OneDrive
    )

# 🗄 FileVault — Local File Manager

A FastAPI-powered file management dashboard with a dark terminal-style UI.

## Features

| Feature | Description |
|---|---|
| **File Explorer** | Browse any directory, sort by name/size/date/type |
| **Batch Delete** | Select multiple files and delete in one click |
| **Duplicate Scanner** | Hash-based detection — finds exact byte-for-byte copies |
| **File Search** | Recursive filename keyword search |
| **Storage Stats** | Live item count and total size per directory |

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the server
python main.py

# 3. Open in browser
http://localhost:8000
```

## How It Works

### Duplicate Detection
Two-pass algorithm for speed:
1. **Pass 1**: Group files by size — only files with identical sizes can be duplicates
2. **Pass 2**: MD5 hash the first + last 64KB of each candidate — full content match

This keeps scanning fast even on large directories (skips hashing unique-size files entirely).

### Delete API
`DELETE /api/delete` accepts a JSON body: `{ "paths": ["..."] }`

Files and entire directories are supported. Results include per-path success/failure.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/roots` | OS-appropriate root paths |
| `GET` | `/api/browse?path=` | List directory contents |
| `GET` | `/api/duplicates?path=` | Find duplicate files |
| `GET` | `/api/search?path=&query=` | Search filenames |
| `DELETE` | `/api/delete` | Delete files/directories |

## ⚠️ Warning

Deletions are **permanent** — there is no Recycle Bin. The UI always shows a confirmation modal before deleting. Run with care on system directories.

## Project Structure

```
file-manager/
├── main.py           # FastAPI backend
├── requirements.txt
└── static/
    └── index.html    # Single-page frontend
```

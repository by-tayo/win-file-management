# 🗄 FileVault — Local File Manager






A FastAPI-powered file management dashboard with UI.


<img width="3830" height="1960" alt="Screenshot 2026-07-18 130007" src="https://github.com/user-attachments/assets/1da3824d-b66a-4429-a2e4-ee96f44a3423" />


---


<img width="3837" height="1980" alt="Screenshot 2026-07-18 130151" src="https://github.com/user-attachments/assets/c0378255-eadc-44ea-87ef-8394c4f378f9" />

---


<img width="3837" height="1970" alt="Screenshot 2026-07-18 130248" src="https://github.com/user-attachments/assets/e5a3de47-35da-4184-a9aa-8bb8dd48bdae" />

---

<img width="3837" height="1985" alt="windows ui 2" src="https://github.com/user-attachments/assets/4601a01e-4632-4136-a567-0de78161d7fc" />

---

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
localhost
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

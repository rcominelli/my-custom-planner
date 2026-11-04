# Hands-on guide (Windows)

Commands to set up, run and maintain the planner generator on the laptop. All commands are
for **PowerShell** and assume the repository is in `C:\RaF\Projects\my-custom-planner`.

> Not yet tested on Windows: the first run is the test. If a step fails, note the exact
> error message.

---

## 1. One-time setup

### 1.1 Install the tools

| Tool | Where | Check |
|------|-------|-------|
| Python 3.11 or newer | python.org, with the "py launcher" option ticked | `py --version` |
| Inkscape 1.3 or newer | inkscape.org, default install folder | `& "C:\Program Files\Inkscape\bin\inkscape.com" --version` |
| Git | git-scm.com | `git --version` |

If Inkscape is installed somewhere else, tell the generator where it is (once per
PowerShell session, or add it as a user environment variable in Windows settings):

```powershell
$env:INKSCAPE = "D:\Apps\Inkscape\bin\inkscape.com"
```

### 1.2 Install the fonts

Open `C:\RaF\Projects\my-custom-planner\fonts`, select all `.otf` and `.ttf` files,
right-click, and choose **Install for all users**. (Inkscape doesn't always see fonts
installed only for the current user.) Restart Inkscape if it was open.

### 1.3 Create the Python environment

The environment (`.venv`) is a private copy of Python with the libraries the generator
needs. It lives in the project folder and is not committed to Git.

```powershell
cd C:\RaF\Projects\my-custom-planner
git pull
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

Check it works:

```powershell
.venv\Scripts\python -m planner --help
```

All commands below call `.venv\Scripts\python` directly, so you never need to activate
the environment.

---

## 2. Generate a month

```powershell
cd C:\RaF\Projects\my-custom-planner
git pull
.venv\Scripts\python -m planner 2026-11
```

Other forms:

```powershell
.venv\Scripts\python -m planner 2027-01 2027-02    # several months
.venv\Scripts\python -m planner 2027               # the whole year
```

The summary is printed on screen and saved as `output\2026-11\report.txt`. Open the
folder with:

```powershell
explorer output\2026-11
```

| File | Use |
|------|-----|
| `planner-2026-11-A5.pdf` | Check on screen, pages in reading order |
| `planner-2026-11-A4-print.pdf` | Print this one |
| `report.txt` | What needs fixing |

### Reading the report

| Line | Meaning | What to do |
|------|---------|------------|
| `No fact for N day(s): ...` | No fact in Excel for those days | Fill them in, or accept an empty fact area |
| `OVERFLOW ... fact text needs about N more line(s)` | The text is cut off on the page | Shorten the text in Excel |
| `OVERFLOW ... title is Npx wider` | The title is wider than the fact text | Shorten the title |
| `OVERFLOW ... source line is wider` | The credit line is too long | Shorten the URL (e.g. drop the `#...` part) or the source name |
| `PICTURE ... cannot use` | The picture file is missing or unreadable | Check the file name in the Image column |
| `WARNING substitute fonts embedded` | Inkscape didn't find the fonts | Repeat step 1.2, then run again |
| `All checks passed` | Ready to print | |

Fix, run the same command again, repeat until the report is clean.

### Printing

Open `planner-YYYY-MM-A4-print.pdf` and print with:

- **double-sided, flip on short edge**
- **actual size** (100%, no "fit")
- A4, landscape

Each sheet carries 4 A5 pages. Cut it in half: the right half holds pages 1-2 of the
group, the left half pages 3-4. Print one sheet first to check the alignment and that
nothing near the edges is cut off. If something is cut off, print with "fit" instead.

---

## 3. Monthly content

### Facts: `data\facts\tech-history.xlsx`

One row per fact, with columns Month, Day, Year, Title, Text, Source, URL, Image.

- **Empty day:** rows without Title and Text are ignored.
- **Several facts for one day:** add more rows with the same Month and Day. The planner
  rotates between them by year.
- **Saving:** save the Excel file before generating, because the generator reads the saved
  version. If you get a `PermissionError`, close the file in Excel.

### Pictures

1. Save the picture (PNG or JPG) in `data\facts\images\`. Name it `MM-DD-short-title.png`
   so the folder stays sorted.
2. Write `images/MM-DD-short-title.png` in the Image column.

The picture is scaled to fit the "Picture area" in the bottom-right corner of the notes
page (at most half the page wide and 90 mm high), keeping its proportions.

### Habits: `planner.toml`

Open it with any text editor. One block per pre-filled row; `priority` is optional:

```toml
[[habits]]
priority = "A0"
text = "Daily planning"
```

---

## 4. Changing the layout

The pages are in `templates\` and are edited with Inkscape:

| File | Page |
|------|------|
| `01-month-cover.svg` | Month cover |
| `02-day-tasks.svg` | Left page of each day |
| `03-day-notes.svg` | Right page of each day |
| `04-month-end.svg` | Last page of the month |

Rules:

- Save as **Inkscape SVG** (not plain SVG).
- Don't rename the labelled fields (Object > Layers and Objects). The list is in
  `README.md` under "Editing". To move or resize a field, just move it.
- Hidden rectangles (`Fact - Text frame`, `Picture area`) set where text wraps and where
  pictures go. To see them, select them in Layers and Objects and turn on visibility.
  Hide them again before saving.

After editing, generate a month again and check the result.

---

## 5. Saving work to GitHub

```powershell
cd C:\RaF\Projects\my-custom-planner
git status
git add -A
git commit -m "Facts for February 2027"
git push
```

Generated PDFs (`output\`) and temporary files (`build\`) are not committed: they can
always be generated again.

---

## 6. Maintenance

| Situation | Command |
|-----------|---------|
| After `git pull`, `requirements.txt` changed | `.venv\Scripts\python -m pip install -r requirements.txt` |
| Python was upgraded, or `.venv` is broken | `Remove-Item -Recurse -Force .venv` then repeat step 1.3 |
| Clear temporary files | `Remove-Item -Recurse -Force build` |

## 7. Troubleshooting

| Error | Fix |
|-------|-----|
| `Inkscape not found` | Install Inkscape, or set `$env:INKSCAPE` (step 1.1) |
| `No module named planner` | Run the command from `C:\RaF\Projects\my-custom-planner` |
| `No module named openpyxl` (or `lxml`, `pypdf`, `PIL`) | Run the pip command from step 1.3 |
| `expected one element labelled '...'` | A template field was renamed or deleted: restore the label in Inkscape |
| Very slow (several minutes per month) | Inkscape's batch mode failed and it fell back to one page at a time. The result is still correct. Report it |

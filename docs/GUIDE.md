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
| `Draft (not yet reviewed) facts printed on ...` | Those days used facts written by Claude that you haven't reviewed | Review them in Excel (section 3.2), or accept them |
| `PICTURE ... cannot use` | The picture file is missing or unreadable | Check the file name in the Image column |
| `WARNING substitute fonts embedded` | Inkscape didn't find the fonts | Repeat step 1.2, then run again |
| `All checks passed` | Ready to print | |

Fix, run the same command again, repeat until the report is clean.

### Printing

Open `planner-YYYY-MM-A4-print.pdf` and print with:

- **double-sided, flip on short edge**
- **page sizing: Fit** (with "Actual size" the printer cuts off content near the edges)
- A4, landscape

Each sheet carries 4 A5 pages. Cut it in half: the right half holds pages 1-2 of the
group, the left half pages 3-4.

---

## 3. Monthly content

### 3.1 Facts file: `data\facts\tech-history.xlsx`

One row per fact, with columns Month, Day, Year, Title, Text, Source, URL, Picture From,
Image, Image Credit, Status. The file doesn't depend on the year: the same facts serve every year.

- **Empty day:** rows without Title and Text are ignored.
- **Several facts for one day** (the goal is 3-4): one row each, same Month and Day. Each
  year the planner prints a different one. It goes through all of them before repeating
  one, in a mixed order that never changes, so rebuilding a month gives the same pages.
- **Saving:** save the Excel file before generating, because the generator reads the saved
  version. If you get a `PermissionError`, close the file in Excel.

**Which fact is printed in which year.** This lists, for every day, the fact chosen in each
year you give, side by side, in `output\facts-2027-2028.csv` (no PDFs are built):

```powershell
.venv\Scripts\python -m planner --list-facts 2027 2028
```

The last column flags days where the same fact appears in more than one of those years.
That happens only when a day has fewer facts than the number of years listed.

### 3.2 Reviewing facts

Facts written by Claude arrive with Status `draft`. Read them, correct anything you like
directly in the cell, then set Status to:

| Status | Effect |
|--------|--------|
| `approved` (or empty) | Printed |
| `draft` | Printed, and listed in the report so you know it wasn't reviewed |
| `rejected` | Never printed (keep the row so it isn't suggested again) |

After editing texts or titles, check that everything still fits (takes about a minute and
covers the whole file, no PDFs built):

```powershell
.venv\Scripts\python -m planner --check-facts
```

### 3.3 Getting new facts

Collecting and writing facts is done with Claude in a cloud session on this repository,
because the writing step needs Claude:

1. Ask Claude to collect and write facts for a month (for example "write tech facts for
   December, 3-4 per day"). Claude runs `python -m collect candidates 12`, writes the
   facts in its own words from the sources, merges them with `python -m collect merge`,
   checks them and pushes the updated Excel file.
2. On the laptop: `git pull`, download the pictures (3.4), then review (3.2).

**One rule:** Git cannot merge two different versions of an Excel file. Before asking
Claude for new facts, commit and push your own changes to the Excel file (section 5), and
`git pull` before editing it again on the laptop.

**Fallback for sites that block automated access:** save the page text by hand as a text
file named `MM-DD-anything.txt` (for example `11-04-compaq.txt`) in
`data\facts\inbox\`, with the page address on the first line. Commit and push it
(section 5). Claude then uses it like any other source.

### 3.4 Pictures

**From Wikipedia (automatic).** The `Picture From` column names a Wikipedia article (or a
Commons file as `File:name.jpg`). This command downloads the article's main picture, only
if it is freely licensed, and fills in Image and Image Credit:

```powershell
.venv\Scripts\python -m collect pictures              # all rows still without a picture
.venv\Scripts\python -m collect pictures --month 11   # only one month
```

Run it on the laptop: Wikipedia limits requests from shared cloud addresses, so it can
stall in a Claude session. Rows where no free picture exists are listed and simply stay
without a picture. To get a different picture, change `Picture From`, clear Image and
Image Credit, and run the command again. The credit is printed in small black text above
the picture. Then commit and push the new pictures and the Excel file (section 5).

**List of facts without a picture.** Exports every fact that has no picture (rejected facts
excluded) to `output\missing-pictures.csv`, which opens in Excel:

```powershell
.venv\Scripts\python -m collect missing              # whole year
.venv\Scripts\python -m collect missing --month 12   # one month
```

The Reason column says whether a `Picture From` was given but no free picture was found
(try another article name, or add your own picture), or no `Picture From` was given at
all. To check again later whether free pictures have become available, just run
`collect pictures` again: it retries every row that still has no picture.

**Your own picture:**

1. Save it (PNG or JPG) in `data\facts\images\`. Name it `MM-DD-short-title.png`
   so the folder stays sorted.
2. Write `images/MM-DD-short-title.png` in the Image column, and the author and license
   in Image Credit if you know them.

The picture is scaled to fit the "Picture area" in the bottom-right corner of the notes
page (at most a third of the page wide and a quarter of the page high), keeping its
proportions, on a white box with a small border that also holds the credit.

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

Always start with `git pull`, before changing or committing anything. If someone else
(for example Claude) pushed in the meantime, your own push would otherwise be refused.

```powershell
cd C:\RaF\Projects\my-custom-planner
git pull
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
| pip shows "A new release of pip is available" | Optional, harmless: `.venv\Scripts\python -m pip install --upgrade pip` |

## 7. Troubleshooting

| Error | Fix |
|-------|-----|
| `Unlink of file '...xlsx' failed. Should I try again?` during `git pull` | The Excel file is open in Excel. Close it, then answer `y` |
| `Cannot write ...: it is open in another program` | Close that PDF (or the Excel file) and run the command again |
| `Corrupt EXIF data` warning during `collect pictures` | Harmless: a picture has damaged camera metadata. Ignore it |
| `git push` refused with `fetch first` | GitHub has commits you don't have. Run `git pull`, then `git push` again |
| `git pull` opens an editor with `MERGE_MSG` | Git is combining your commits with new ones from GitHub. Close the tab without changes, then `git push` |
| `Inkscape not found` | Install Inkscape, or set `$env:INKSCAPE` (step 1.1) |
| `No module named planner` | Run the command from `C:\RaF\Projects\my-custom-planner` |
| `No module named openpyxl` (or `lxml`, `pypdf`, `PIL`) | Run the pip command from step 1.3 |
| `expected one element labelled '...'` | A template field was renamed or deleted: restore the label in Inkscape |
| Very slow (several minutes per month) | Inkscape's batch mode failed and it fell back to one page at a time. The result is still correct. Report it |

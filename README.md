# Binairo Solver

Automated solver and interactive UI for Binairo (also known as Takuzu / Binary Puzzle) and Binairo+ (with equality `=` and negation `x` adjacent cell comparison constraints).

## Features

- **Userscript & Bookmarklet (`binairo_web_solver.js` / `bookmarklet.txt`)**:
  - Solves puzzles live on [puzzle-binairo.com](https://www.puzzle-binairo.com/) automatically or on demand.
  - Full support for **Binairo+** comparison clues (`eqv`, `eqh`, `nev`, `neh`).
  - Auto-watcher detects new/unsolved boards and solves instantly.
  - Interactive on-screen control toggle (`⚡ Auto: ON/OFF`).
- **Python Interactive Web App (`app.py`, `game.py`)**:
  - Local browser-based visualizer and solver.
  - Step-by-step deduction rules (3-in-a-row prevention, balance counts, line elimination, and backtracking search).
  - Ability to parse and load boards directly from HTML / DOM snippets.

## Usage

### Web Userscript / Bookmarklet
1. Install `binairo_web_solver.js` with Tampermonkey / Violentmonkey, OR copy the contents of `bookmarklet.txt` into a browser bookmark.
2. Navigate to [puzzle-binairo.com](https://www.puzzle-binairo.com/).
3. The solver will automatically detect boards and solve them instantly (or click the green floating button).

### Local Python Server
```bash
python3 app.py
```
Open `http://localhost:8000` in your web browser.

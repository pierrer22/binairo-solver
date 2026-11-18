// ==UserScript==
// @name         Puzzle Binairo Auto-Solver (Standard & Binairo+)
// @namespace    https://www.puzzle-binairo.com/
// @version      5.0
// @description  Instantly solves standard Binairo and Binairo+ (equal/opposing symbols) on puzzle-binairo.com
// @match        https://*.puzzle-binairo.com/*
// @grant        none
// ==/UserScript==

(function() {
  'use strict';

  let autoSolveEnabled = true;
  let lastSolvedPuzzleId = null;

  function solveBinairoWeb(animated = false, stepDelay = 10) {
    const boardBack = document.querySelector('.board-back');
    if (!boardBack && (!window.Game || !window.Game.task)) {
      return false;
    }

    let H, W, grid, cellElements;
    const comparisons = []; // List of { r1, c1, r2, c2, type: 'EQ' | 'NE' }

    if (window.Game && window.Game.task && window.Game.task.length) {
      H = window.Game.task.length;
      W = window.Game.task[0].length;
      grid = Array.from({ length: H }, () => Array(W).fill(-1));
      for (let y = 0; y < H; y++) {
        for (let x = 0; x < W; x++) {
          const t = window.Game.task[y][x];
          // On puzzle-binairo.com: 1 = black circle (cell-1), 0 = white circle (cell-0), -1 = empty
          if (t === 1) grid[y][x] = 1;
          else if (t === 0) grid[y][x] = 0;
        }
      }

      // Read comparison clues directly from window.Game if available (Binairo+)
      if (window.Game.comparisonClues && window.Game.comparisonClues.length) {
        const FLAG_RIGHT_EQ = 1;
        const FLAG_RIGHT_NE = 2;
        const FLAG_DOWN_EQ = 4;
        const FLAG_DOWN_NE = 8;
        for (let y = 0; y < H; y++) {
          for (let x = 0; x < W; x++) {
            const flag = window.Game.comparisonClues[y][x] || 0;
            if (flag & FLAG_RIGHT_EQ) comparisons.push({ r1: y, c1: x, r2: y, c2: x + 1, type: 'EQ' });
            if (flag & FLAG_RIGHT_NE) comparisons.push({ r1: y, c1: x, r2: y, c2: x + 1, type: 'NE' });
            if (flag & FLAG_DOWN_EQ) comparisons.push({ r1: y, c1: x, r2: y + 1, c2: x, type: 'EQ' });
            if (flag & FLAG_DOWN_NE) comparisons.push({ r1: y, c1: x, r2: y + 1, c2: x, type: 'NE' });
          }
        }
      }
    } else {
      // Parse from .board-back DOM elements
      const cellNodes = Array.from(boardBack.querySelectorAll('.cell, .task-cell'));
      const parsed = cellNodes.map(el => {
        const top = parseInt(el.style.top);
        const left = parseInt(el.style.left);
        return { el, top, left, cls: el.className };
      });

      const rowsY = [...new Set(parsed.map(c => c.top))].sort((a,b) => a - b);
      const colsX = [...new Set(parsed.map(c => c.left))].sort((a,b) => a - b);
      H = rowsY.length;
      W = colsX.length;
      const yMap = Object.fromEntries(rowsY.map((y, i) => [y, i]));
      const xMap = Object.fromEntries(colsX.map((x, i) => [x, i]));

      grid = Array.from({ length: H }, () => Array(W).fill(-1));
      cellElements = Array.from({ length: H }, () => Array(W).fill(null));

      for (const c of parsed) {
        const y = yMap[c.top];
        const x = xMap[c.left];
        cellElements[y][x] = c.el;
        // ONLY treat task-cell (initial clues) as fixed clues!
        if (c.cls.includes('task-cell')) {
          if (c.cls.includes('cell-1')) grid[y][x] = 1;
          else if (c.cls.includes('cell-0')) grid[y][x] = 0;
        }
      }

      // Parse Binairo+ comparison clues from DOM (.comparison-clue)
      function findClosestIdx(arr, val) {
        let best = 0, bestDiff = Infinity;
        for (let i = 0; i < arr.length; i++) {
          const diff = Math.abs(arr[i] - val);
          if (diff < bestDiff) { bestDiff = diff; best = i; }
        }
        return best;
      }
      function findBeforeIdx(arr, val) {
        for (let i = 0; i < arr.length - 1; i++) {
          if (val >= arr[i] - 5 && val <= arr[i+1] + 5) return i;
        }
        return 0;
      }

      const compNodes = Array.from(boardBack.querySelectorAll('.comparison-clue'));
      for (const el of compNodes) {
        const top = parseInt(el.style.top);
        const left = parseInt(el.style.left);
        const cls = el.className;
        const isHoriz = cls.includes('eqv') || cls.includes('nev');
        const isVert = cls.includes('eqh') || cls.includes('neh');
        const isEq = cls.includes('eqv') || cls.includes('eqh');
        const type = isEq ? 'EQ' : 'NE';

        if (isHoriz) {
          const r = findClosestIdx(rowsY, top);
          const c = findBeforeIdx(colsX, left);
          comparisons.push({ r1: r, c1: c, r2: r, c2: c + 1, type });
        } else if (isVert) {
          const c = findClosestIdx(colsX, left);
          const r = findBeforeIdx(rowsY, top);
          comparisons.push({ r1: r, c1: c, r2: r + 1, c2: c, type });
        }
      }
    }

    const maxR = W / 2;
    const maxC = H / 2;

    // --- SOLVER ENGINE ---
    function basicPropagate(g) {
      let changed = true;
      while (changed) {
        changed = false;

        // 0. Explicit contradiction check: no 3 in a row among existing filled cells
        for (let y = 0; y < H; y++) {
          for (let x = 0; x < W; x++) {
            if (g[y][x] === -1) continue;
            if (x >= 2 && g[y][x] === g[y][x - 1] && g[y][x] === g[y][x - 2]) return false;
            if (y >= 2 && g[y][x] === g[y - 1][x] && g[y][x] === g[y - 2][x]) return false;
          }
        }

        // 1. Direct Equal/Opposing enforcement
        for (const comp of comparisons) {
          const v1 = g[comp.r1][comp.c1];
          const v2 = g[comp.r2][comp.c2];
          if (comp.type === 'EQ') {
            if (v1 !== -1 && v2 !== -1) {
              if (v1 !== v2) return false; // Contradiction!
            } else if (v1 !== -1 && v2 === -1) {
              g[comp.r2][comp.c2] = v1;
              changed = true;
            } else if (v2 !== -1 && v1 === -1) {
              g[comp.r1][comp.c1] = v2;
              changed = true;
            }
          } else if (comp.type === 'NE') {
            if (v1 !== -1 && v2 !== -1) {
              if (v1 === v2) return false; // Contradiction!
            } else if (v1 !== -1 && v2 === -1) {
              g[comp.r2][comp.c2] = 1 - v1;
              changed = true;
            } else if (v2 !== -1 && v1 === -1) {
              g[comp.r1][comp.c1] = 1 - v2;
              changed = true;
            }
          }
        }

        // 2. Rule: B _ = _ => B W = W and _ = _ B => W = W B (and W _ = _ => W B = B)
        // Two equal cells adjacent to a cell V cannot be V (otherwise 3 in a row V V V)
        for (const comp of comparisons) {
          if (comp.type === 'EQ') {
            if (comp.r1 === comp.r2 && comp.c2 === comp.c1 + 1) { // Horizontal EQ
              const y = comp.r1, c1 = comp.c1, c2 = comp.c2;
              if (c1 > 0 && g[y][c1 - 1] !== -1) {
                const forced = 1 - g[y][c1 - 1];
                if (g[y][c1] === -1) { g[y][c1] = forced; changed = true; }
                if (g[y][c2] === -1) { g[y][c2] = forced; changed = true; }
                if (g[y][c1] !== forced || g[y][c2] !== forced) return false;
              }
              if (c2 + 1 < W && g[y][c2 + 1] !== -1) {
                const forced = 1 - g[y][c2 + 1];
                if (g[y][c1] === -1) { g[y][c1] = forced; changed = true; }
                if (g[y][c2] === -1) { g[y][c2] = forced; changed = true; }
                if (g[y][c1] !== forced || g[y][c2] !== forced) return false;
              }
            }
            if (comp.c1 === comp.c2 && comp.r2 === comp.r1 + 1) { // Vertical EQ
              const x = comp.c1, r1 = comp.r1, r2 = comp.r2;
              if (r1 > 0 && g[r1 - 1][x] !== -1) {
                const forced = 1 - g[r1 - 1][x];
                if (g[r1][x] === -1) { g[r1][x] = forced; changed = true; }
                if (g[r2][x] === -1) { g[r2][x] = forced; changed = true; }
                if (g[r1][x] !== forced || g[r2][x] !== forced) return false;
              }
              if (r2 + 1 < H && g[r2 + 1][x] !== -1) {
                const forced = 1 - g[r2 + 1][x];
                if (g[r1][x] === -1) { g[r1][x] = forced; changed = true; }
                if (g[r2][x] === -1) { g[r2][x] = forced; changed = true; }
                if (g[r1][x] !== forced || g[r2][x] !== forced) return false;
              }
            }
          }
        }

        // 3. Rule: V V [ _ x _ ] => V V (1-V) x V and [ _ x _ ] V V => V x (1-V) V V
        for (const comp of comparisons) {
          if (comp.type === 'NE') {
            if (comp.r1 === comp.r2 && comp.c2 === comp.c1 + 1) { // Horizontal NE
              const y = comp.r1, c1 = comp.c1, c2 = comp.c2;
              if (c1 >= 2 && g[y][c1 - 1] !== -1 && g[y][c1 - 1] === g[y][c1 - 2]) {
                const opp = 1 - g[y][c1 - 1];
                if (g[y][c1] === -1) { g[y][c1] = opp; changed = true; }
                if (g[y][c2] === -1) { g[y][c2] = 1 - opp; changed = true; }
                if (g[y][c1] !== opp || g[y][c2] !== 1 - opp) return false;
              }
              if (c2 + 2 < W && g[y][c2 + 1] !== -1 && g[y][c2 + 1] === g[y][c2 + 2]) {
                const opp = 1 - g[y][c2 + 1];
                if (g[y][c2] === -1) { g[y][c2] = opp; changed = true; }
                if (g[y][c1] === -1) { g[y][c1] = 1 - opp; changed = true; }
                if (g[y][c2] !== opp || g[y][c1] !== 1 - opp) return false;
              }
            }
            if (comp.c1 === comp.c2 && comp.r2 === comp.r1 + 1) { // Vertical NE
              const x = comp.c1, r1 = comp.r1, r2 = comp.r2;
              if (r1 >= 2 && g[r1 - 1][x] !== -1 && g[r1 - 1][x] === g[r1 - 2][x]) {
                const opp = 1 - g[r1 - 1][x];
                if (g[r1][x] === -1) { g[r1][x] = opp; changed = true; }
                if (g[r2][x] === -1) { g[r2][x] = 1 - opp; changed = true; }
                if (g[r1][x] !== opp || g[r2][x] !== 1 - opp) return false;
              }
              if (r2 + 2 < H && g[r2 + 1][x] !== -1 && g[r2 + 1][x] === g[r2 + 2][x]) {
                const opp = 1 - g[r2 + 1][x];
                if (g[r2][x] === -1) { g[r2][x] = opp; changed = true; }
                if (g[r1][x] === -1) { g[r1][x] = 1 - opp; changed = true; }
                if (g[r2][x] !== opp || g[r1][x] !== 1 - opp) return false;
              }
            }
          }
        }

        // 4. Rule: _x_ pairs consume 1 of each value in line quota
        for (let y = 0; y < H; y++) {
          const nePairs = comparisons.filter(c => c.type === 'NE' && c.r1 === y && c.r2 === y && g[y][c.c1] === -1 && g[y][c.c2] === -1);
          if (nePairs.length > 0) {
            let c0 = 0, c1 = 0;
            for (let x = 0; x < W; x++) { if (g[y][x] === 0) c0++; else if (g[y][x] === 1) c1++; }
            const rem0 = maxR - c0, rem1 = maxR - c1;
            const k = nePairs.length;
            const inPairs = new Set(nePairs.flatMap(p => [p.c1, p.c2]));
            if (rem0 === k && rem0 > 0) {
              for (let x = 0; x < W; x++) {
                if (g[y][x] === -1 && !inPairs.has(x)) { g[y][x] = 1; changed = true; }
              }
            }
            if (rem1 === k && rem1 > 0) {
              for (let x = 0; x < W; x++) {
                if (g[y][x] === -1 && !inPairs.has(x)) { g[y][x] = 0; changed = true; }
              }
            }
          }
        }
        for (let x = 0; x < W; x++) {
          const nePairs = comparisons.filter(c => c.type === 'NE' && c.c1 === x && c.c2 === x && g[c.r1][x] === -1 && g[c.r2][x] === -1);
          if (nePairs.length > 0) {
            let c0 = 0, c1 = 0;
            for (let y = 0; y < H; y++) { if (g[y][x] === 0) c0++; else if (g[y][x] === 1) c1++; }
            const rem0 = maxC - c0, rem1 = maxC - c1;
            const k = nePairs.length;
            const inPairs = new Set(nePairs.flatMap(p => [p.r1, p.r2]));
            if (rem0 === k && rem0 > 0) {
              for (let y = 0; y < H; y++) {
                if (g[y][x] === -1 && !inPairs.has(y)) { g[y][x] = 1; changed = true; }
              }
            }
            if (rem1 === k && rem1 > 0) {
              for (let y = 0; y < H; y++) {
                if (g[y][x] === -1 && !inPairs.has(y)) { g[y][x] = 0; changed = true; }
              }
            }
          }
        }

        // 5. Quota constraints
        for (let y = 0; y < H; y++) {
          let c0 = 0, c1 = 0;
          for (let x = 0; x < W; x++) { if (g[y][x] === 0) c0++; else if (g[y][x] === 1) c1++; }
          if (c0 > maxR || c1 > maxR) return false;
          if (c0 === maxR) {
            for (let x = 0; x < W; x++) if (g[y][x] === -1) { g[y][x] = 1; changed = true; }
          } else if (c1 === maxR) {
            for (let x = 0; x < W; x++) if (g[y][x] === -1) { g[y][x] = 0; changed = true; }
          }
        }
        for (let x = 0; x < W; x++) {
          let c0 = 0, c1 = 0;
          for (let y = 0; y < H; y++) { if (g[y][x] === 0) c0++; else if (g[y][x] === 1) c1++; }
          if (c0 > maxC || c1 > maxC) return false;
          if (c0 === maxC) {
            for (let y = 0; y < H; y++) if (g[y][x] === -1) { g[y][x] = 1; changed = true; }
          } else if (c1 === maxC) {
            for (let y = 0; y < H; y++) if (g[y][x] === -1) { g[y][x] = 0; changed = true; }
          }
        }

        // 6. No three in a row (horizontal & vertical)
        for (let y = 0; y < H; y++) {
          for (let x = 0; x < W; x++) {
            if (g[y][x] !== -1) continue;
            let can0 = true, can1 = true;
            // horizontal
            if ((x >= 2 && g[y][x-1] === 0 && g[y][x-2] === 0) ||
                (x <= W-3 && g[y][x+1] === 0 && g[y][x+2] === 0) ||
                (x >= 1 && x <= W-2 && g[y][x-1] === 0 && g[y][x+1] === 0) ||
                (y >= 2 && g[y-1][x] === 0 && g[y-2][x] === 0) ||
                (y <= H-3 && g[y+1][x] === 0 && g[y+2][x] === 0) ||
                (y >= 1 && y <= H-2 && g[y-1][x] === 0 && g[y+1][x] === 0)) can0 = false;

            if ((x >= 2 && g[y][x-1] === 1 && g[y][x-2] === 1) ||
                (x <= W-3 && g[y][x+1] === 1 && g[y][x+2] === 1) ||
                (x >= 1 && x <= W-2 && g[y][x-1] === 1 && g[y][x+1] === 1) ||
                (y >= 2 && g[y-1][x] === 1 && g[y-2][x] === 1) ||
                (y <= H-3 && g[y+1][x] === 1 && g[y+2][x] === 1) ||
                (y >= 1 && y <= H-2 && g[y-1][x] === 1 && g[y+1][x] === 1)) can1 = false;

            if (!can0 && !can1) return false;
            if (can0 && !can1) { g[y][x] = 0; changed = true; }
            else if (can1 && !can0) { g[y][x] = 1; changed = true; }
          }
        }
      }
      return true;
    }

    // Combination consistency deduction with line-internal comparisons
    function deduceCombinations(line, maxPieces, lineComps = []) {
      const empty = [];
      let c0 = 0, c1 = 0;
      for (let i = 0; i < line.length; i++) {
        if (line[i] === 0) c0++;
        else if (line[i] === 1) c1++;
        else empty.push(i);
      }
      if (!empty.length || empty.length > 18) return {};
      const rem1 = maxPieces - c1;
      if (rem1 < 0 || (maxPieces - c0) < 0) return {};
      const valid = [];
      function comb(idx, onesCount, current) {
        if (onesCount > rem1) return;
        if (current.length - onesCount > maxPieces - c0) return;
        if (idx === empty.length) {
          if (onesCount === rem1) {
            const full = [...line];
            empty.forEach((pos, i) => full[pos] = current[i]);
            let ok = true;
            for (let i = 0; i < full.length - 2; i++) {
              if (full[i] === full[i+1] && full[i] === full[i+2]) { ok = false; break; }
            }
            if (ok) {
              for (const lc of lineComps) {
                if (lc.type === 'EQ' && full[lc.p1] !== full[lc.p2]) { ok = false; break; }
                if (lc.type === 'NE' && full[lc.p1] === full[lc.p2]) { ok = false; break; }
              }
            }
            if (ok) valid.push(full);
          }
          return;
        }
        current.push(1);
        comb(idx + 1, onesCount + 1, current);
        current.pop();
        current.push(0);
        comb(idx + 1, onesCount, current);
        current.pop();
      }
      comb(0, 0, []);
      if (!valid.length) return {};
      const deds = {};
      for (const pos of empty) {
        const v = valid[0][pos];
        if (valid.every(sol => sol[pos] === v)) deds[pos] = v;
      }
      return deds;
    }

    function stepDeductions(board) {
      while (true) {
        if (!basicPropagate(board)) return false;
        let c = 0;
        for (let y = 0; y < H; y++) {
          const rowComps = comparisons
            .filter(cp => cp.r1 === y && cp.r2 === y)
            .map(cp => ({ p1: cp.c1, p2: cp.c2, type: cp.type }));
          const d = deduceCombinations(board[y], maxR, rowComps);
          for (const [x, val] of Object.entries(d)) {
            if (board[y][x] === -1) { board[y][x] = val; c++; }
          }
        }
        for (let x = 0; x < W; x++) {
          const col = board.map(r => r[x]);
          const colComps = comparisons
            .filter(cp => cp.c1 === x && cp.c2 === x)
            .map(cp => ({ p1: cp.r1, p2: cp.r2, type: cp.type }));
          const d = deduceCombinations(col, maxC, colComps);
          for (const [y, val] of Object.entries(d)) {
            if (board[y][x] === -1) { board[y][x] = val; c++; }
          }
        }
        if (!c) break;
      }
      return true;
    }

    function checkUnique(board) {
      const rows = new Set();
      for (let y = 0; y < H; y++) {
        if (!board[y].includes(-1)) {
          const s = board[y].join("");
          if (rows.has(s)) return false;
          rows.add(s);
        }
      }
      const cols = new Set();
      for (let x = 0; x < W; x++) {
        let full = true;
        let s = "";
        for (let y = 0; y < H; y++) {
          if (board[y][x] === -1) { full = false; break; }
          s += board[y][x];
        }
        if (full) {
          if (cols.has(s)) return false;
          cols.add(s);
        }
      }
      return true;
    }

    function search(board) {
      if (!stepDeductions(board)) return null;
      if (!checkUnique(board)) return null;

      let bestY = -1, bestX = -1;
      for (let y = 0; y < H; y++) {
        for (let x = 0; x < W; x++) {
          if (board[y][x] === -1) {
            bestY = y; bestX = x; break;
          }
        }
        if (bestY !== -1) break;
      }
      if (bestY === -1) {
        // Final safety check: ensure no 3-in-a-row exists anywhere
        for (let y = 0; y < H; y++) {
          for (let x = 0; x < W; x++) {
            if (x >= 2 && board[y][x] === board[y][x - 1] && board[y][x] === board[y][x - 2]) return null;
            if (y >= 2 && board[y][x] === board[y - 1][x] && board[y][x] === board[y - 2][x]) return null;
          }
        }
        return board; // Solved completely!
      }

      for (const v of [0, 1]) {
        const copy = board.map(r => [...r]);
        copy[bestY][bestX] = v;
        const res = search(copy);
        if (res) return res;
      }
      return null;
    }

    const tStart = performance.now();
    const solution = search(grid);

    if (!solution) {
      console.warn("[Binairo Solver] Could not solve puzzle.");
      return false;
    }

    console.log(`[Binairo Solver] Solved 100% in ${(performance.now() - tStart).toFixed(1)}ms!`);

    // --- APPLY SOLUTION TO WEBPAGE ---
    const movesToApply = [];
    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        // Skip fixed clues from initial task
        if (window.Game && window.Game.task && window.Game.task[y][x] !== -1) continue;
        const val = solution[y][x];
        if (val === 0 || val === 1) {
          movesToApply.push({ y, x, val });
        }
      }
    }

    function applySingleMove(move) {
      const { y, x, val } = move;
      if (val !== 0 && val !== 1) return; // Strict safety

      // On puzzle-binairo.com: 1 = black circle (cell-1), 2 = white circle (cell-0)
      const siteVal = (val === 1 ? 1 : 2);
      if (window.Game && window.Game.currentState) {
        window.Game.currentState.cellStatus[y][x] = siteVal;
        if (window.Game.drawCellStatus) {
          window.Game.drawCellStatus({ row: y, col: x }, siteVal);
        }
      } else if (cellElements && cellElements[y][x]) {
        const el = cellElements[y][x];
        el.classList.remove('cell-off', 'cell-0', 'cell-1', 'err');
        el.classList.add(siteVal === 1 ? 'cell-1' : 'cell-0');
      }
    }

    function finalizeBoard() {
      if (window.Game) {
        if (window.Game.checkComparison) window.Game.checkComparison();
        if (window.Game.updateCounters) window.Game.updateCounters();
        if (window.Game.check3InARow) window.Game.check3InARow();
        if (window.Game.checkFinished) window.Game.checkFinished();
      }
    }

    if (!animated) {
      for (const move of movesToApply) {
        applySingleMove(move);
      }
      finalizeBoard();
    } else {
      let i = 0;
      const timer = setInterval(() => {
        if (i >= movesToApply.length) {
          clearInterval(timer);
          finalizeBoard();
          return;
        }
        applySingleMove(movesToApply[i++]);
        if (window.Game && window.Game.updateCounters) window.Game.updateCounters();
      }, stepDelay);
    }
    return true;
  }

  // Helper functions for automatic puzzle detection
  function getPuzzleFingerprint() {
    let key = '';
    if (window.Game && window.Game.task && window.Game.task.length) {
      key += window.Game.task.map(r => r.join(',')).join(';');
      if (window.Game.comparisonClues && window.Game.comparisonClues.length) {
        key += '|' + window.Game.comparisonClues.map(r => r.join(',')).join(';');
      }
      return key;
    }
    const boardBack = document.querySelector('.board-back');
    if (boardBack) {
      const taskCells = boardBack.querySelectorAll('.task-cell');
      const compCells = boardBack.querySelectorAll('.comparison-clue');
      if (taskCells.length || compCells.length) {
        key += Array.from(taskCells).map(c => `${c.style.top},${c.style.left},${c.className}`).join('|');
        key += '||' + Array.from(compCells).map(c => `${c.style.top},${c.style.left},${c.className}`).join('|');
        return key;
      }
    }
    return null;
  }

  function isBoardUnsolved() {
    if (window.Game && window.Game.currentState && window.Game.currentState.cellStatus) {
      if (window.Game.currentState.solved || window.Game.solved) return false;
      for (const row of window.Game.currentState.cellStatus) {
        if (row.includes(0)) return true; // 0 represents empty status in Game.currentState.cellStatus
      }
      // If filled but game is NOT marked solved: it means it contains mistakes/unsolved!
      return true;
    }
    const boardBack = document.querySelector('.board-back');
    if (boardBack) {
      if (boardBack.querySelector('.cell-off') !== null) return true;
      if (boardBack.querySelector('.err') !== null) return true;
    }
    return false;
  }

  function updateButtonUI() {
    const btn = document.getElementById('binairo-auto-solve-btn');
    if (!btn) return;
    if (autoSolveEnabled) {
      btn.textContent = '⚡ Auto: ON (Instant)';
      btn.style.background = '#059669';
      btn.style.borderColor = '#34d399';
    } else {
      btn.textContent = '⚡ Auto: OFF (Click)';
      btn.style.background = '#4b5563';
      btn.style.borderColor = '#9ca3af';
    }
  }

  // Automatic watcher loop: triggers instant solve whenever an unsolved board is spotted
  function checkAndAutoSolve() {
    if (!autoSolveEnabled) return;
    const fingerprint = getPuzzleFingerprint();
    if (!fingerprint) return;

    if (fingerprint !== lastSolvedPuzzleId && isBoardUnsolved()) {
      console.log('[Binairo Auto-Solver] Unsolved board spotted! Solving instantly...');
      const ok = solveBinairoWeb(false);
      if (ok) {
        lastSolvedPuzzleId = fingerprint;
      }
      updateButtonUI();
    }
  }

  // Inject floating UI button onto the webpage with toggle
  function injectButton() {
    if (document.getElementById('binairo-auto-solve-btn')) return;
    const btn = document.createElement('button');
    btn.id = 'binairo-auto-solve-btn';
    btn.title = 'Click to toggle auto-solve on/off. Shift+Click to force instant solve.';
    btn.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      z-index: 999999;
      color: #fff;
      border: 2px solid;
      border-radius: 8px;
      padding: 10px 18px;
      font-size: 14px;
      font-weight: bold;
      cursor: pointer;
      box-shadow: 0 4px 14px rgba(0,0,0,0.4);
      font-family: sans-serif;
      transition: all 0.2s ease;
      user-select: none;
    `;

    btn.onclick = (e) => {
      if (e.shiftKey) {
        // Force manual solve
        solveBinairoWeb(false);
      } else {
        // Toggle auto-solve mode
        autoSolveEnabled = !autoSolveEnabled;
        updateButtonUI();
        if (autoSolveEnabled) {
          checkAndAutoSolve();
        }
      }
    };

    document.body.appendChild(btn);
    updateButtonUI();
  }

  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    injectButton();
  } else {
    window.addEventListener('DOMContentLoaded', injectButton);
  }

  // Run watcher immediately and poll every 250ms to catch new puzzles immediately
  setInterval(checkAndAutoSolve, 250);

  window.solveBinairoWeb = solveBinairoWeb;
})();
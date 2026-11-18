#!/usr/bin/env python3
import itertools
import json
import os
import re
import sys
import webbrowser
from math import comb
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from game import load_grid_from_html, Node

# Default sample 10x10 puzzle if no board.txt
DEFAULT_10x10 = [
    [-1, 1, -1, -1, -1, 0, -1, -1, 0, -1],
    [-1, -1, -1, 0, 1, -1, -1, -1, -1, 1],
    [-1, -1, -1, 0, -1, -1, -1, -1, -1, -1],
    [-1, -1, 1, -1, -1, -1, -1, -1, -1, -1],
    [0, -1, -1, 1, -1, -1, 1, -1, -1, -1],
    [-1, 1, -1, -1, -1, -1, -1, 0, -1, -1],
    [-1, 0, -1, -1, -1, 1, 1, -1, 0, -1],
    [-1, -1, -1, 1, -1, -1, -1, -1, -1, -1],
    [-1, 1, -1, -1, -1, -1, 1, -1, 1, -1],
    [-1, -1, 0, -1, -1, -1, -1, -1, 1, 1]
]

class GameState:
    def __init__(self):
        self.board_name = "board.txt"
        self.load_from_file_or_default("board.txt")

    def load_from_file_or_default(self, filepath="board.txt"):
        if os.path.exists(filepath):
            self.initial_values, self.width, self.height = load_grid_from_html(filepath)
            self.board_name = os.path.basename(filepath)
        else:
            self.initial_values = [row[:] for row in DEFAULT_10x10]
            self.width = 10
            self.height = 10
            self.board_name = "Default 10x10"

        self.max_row = self.width // 2
        self.max_col = self.height // 2
        self.reset()

    def load_from_html_string(self, html_content, name="Custom HTML"):
        pattern = re.compile(
            r'<div[^>]*style=\"[^\"]*top:\s*(\d+)px;\s*left:\s*(\d+)px;[^\"]*\"[^>]*class=\"([^\"]*(?:cell-off|cell-0|cell-1)[^\"]*)\"',
            re.IGNORECASE
        )
        matches = pattern.findall(html_content)
        if not matches:
            pattern = re.compile(
                r'<div[^>]*class=\"([^\"]*(?:cell-off|cell-0|cell-1)[^\"]*)\"[^>]*style=\"[^\"]*top:\s*(\d+)px;\s*left:\s*(\d+)px;[^\"]*\"',
                re.IGNORECASE
            )
            matches = [(m[1], m[2], m[0]) for m in pattern.findall(html_content)]

        if not matches:
            return False, "Could not find any valid cell divs in the HTML."

        rows_y = sorted(list({int(m[0]) for m in matches}))
        cols_x = sorted(list({int(m[1]) for m in matches}))
        height = len(rows_y)
        width = len(cols_x)
        y_map = {top: i for i, top in enumerate(rows_y)}
        x_map = {left: i for i, left in enumerate(cols_x)}

        grid_values = [[-1 for _ in range(width)] for _ in range(height)]
        for top_str, left_str, cls in matches:
            y = y_map[int(top_str)]
            x = x_map[int(left_str)]
            if 'task-cell' in cls:
                if 'cell-1' in cls: grid_values[y][x] = 1
                elif 'cell-0' in cls: grid_values[y][x] = 0

        self.initial_values = grid_values
        self.width = width
        self.height = height
        self.max_row = width // 2
        self.max_col = height // 2
        self.board_name = name
        self.reset()
        return True, f"Loaded {width}x{height} puzzle successfully."

    def reset(self):
        self.nodes = [[Node(x, y) for x in range(self.width)] for y in range(self.height)]
        for y in range(self.height):
            for x in range(self.width):
                val = self.initial_values[y][x]
                if val == 1:
                    self.nodes[y][x].value = 'X'
                elif val == 0:
                    self.nodes[y][x].value = 'O'
                else:
                    self.nodes[y][x].value = ' '

        # connect neighbors
        for y in range(self.height):
            for x in range(self.width):
                if y > 0: self.nodes[y][x].north = self.nodes[y-1][x]
                if y < self.height - 1: self.nodes[y][x].south = self.nodes[y+1][x]
                if x > 0: self.nodes[y][x].west = self.nodes[y][x-1]
                if x < self.width - 1: self.nodes[y][x].east = self.nodes[y][x+1]

    def count_pieces(self, node):
        row_x = 1 if node.value == 'X' else 0
        row_o = 1 if node.value == 'O' else 0
        col_x = row_x
        col_o = row_o

        curr = node.west
        while curr:
            if curr.value == 'X': row_x += 1
            elif curr.value == 'O': row_o += 1
            curr = curr.west
        curr = node.east
        while curr:
            if curr.value == 'X': row_x += 1
            elif curr.value == 'O': row_o += 1
            curr = curr.east

        curr = node.north
        while curr:
            if curr.value == 'X': col_x += 1
            elif curr.value == 'O': col_o += 1
            curr = curr.north
        curr = node.south
        while curr:
            if curr.value == 'X': col_x += 1
            elif curr.value == 'O': col_o += 1
            curr = curr.south

        return (row_x, row_o), (col_x, col_o)

    def exceeds_max_pieces(self, node):
        (row_x, row_o), (col_x, col_o) = self.count_pieces(node)
        return (row_x > self.max_row or row_o > self.max_row or
                col_x > self.max_col or col_o > self.max_col)

    def three_in_a_row(self, node):
        if node.value not in ('X', 'O'):
            return False

        # horizontal
        count = 1
        curr = node.west
        while curr and curr.value == node.value:
            count += 1
            curr = curr.west
        curr = node.east
        while curr and curr.value == node.value:
            count += 1
            curr = curr.east
        if count >= 3:
            return True

        # vertical
        count = 1
        curr = node.north
        while curr and curr.value == node.value:
            count += 1
            curr = curr.north
        curr = node.south
        while curr and curr.value == node.value:
            count += 1
            curr = curr.south
        return count >= 3

    def is_invalid_move(self, node, value):
        orig = node.value
        node.value = value
        invalid = self.three_in_a_row(node) or self.exceeds_max_pieces(node)
        node.value = orig
        return invalid

    def deduce_patterns_for_line(self, nodes, max_pieces, line_name=''):
        vals = [n.value for n in nodes]
        cnt_x = vals.count('X')
        cnt_o = vals.count('O')
        rem_x = max_pieces - cnt_x
        rem_o = max_pieces - cnt_o
        empty_indices = [i for i, v in enumerate(vals) if v == ' ']
        if not empty_indices:
            return []

        reqs_x = []
        reqs_o = []
        n = len(vals)

        # 1. X--X must contain at least one O
        # 2. O--O must contain at least one X
        # 3. X--O or O--X must contain at least one X and one O
        for i in range(n - 3):
            if vals[i+1] == ' ' and vals[i+2] == ' ':
                pair = {i+1, i+2}
                if vals[i] == 'X' and vals[i+3] == 'X':
                    reqs_o.append((pair, 'X--X requires at least one O'))
                elif vals[i] == 'O' and vals[i+3] == 'O':
                    reqs_x.append((pair, 'O--O requires at least one X'))
                elif (vals[i] == 'X' and vals[i+3] == 'O') or (vals[i] == 'O' and vals[i+3] == 'X'):
                    reqs_x.append((pair, 'X--O / O--X requires at least one X and one O'))
                    reqs_o.append((pair, 'X--O / O--X requires at least one X and one O'))

        # 4. Three consecutive blanks must contain at least one X and one O
        for i in range(n - 2):
            if vals[i] == ' ' and vals[i+1] == ' ' and vals[i+2] == ' ':
                triplet = {i, i+1, i+2}
                reqs_x.append((triplet, 'three consecutive blanks require at least one X and one O'))
                reqs_o.append((triplet, 'three consecutive blanks require at least one X and one O'))

        def max_disjoint(req_list):
            if not req_list: return ()
            sorted_reqs = sorted(req_list, key=lambda item: len(item[0]))
            for r in range(len(sorted_reqs), 0, -1):
                for comb_items in itertools.combinations(sorted_reqs, r):
                    seen = set()
                    disjoint = True
                    for s, _ in comb_items:
                        if seen & s:
                            disjoint = False
                            break
                        seen |= s
                    if disjoint:
                        return comb_items
            return ()

        placed = []
        disjoint_x = max_disjoint(reqs_x)
        if len(disjoint_x) == rem_x and rem_x > 0:
            covered = set().union(*(s for s, _ in disjoint_x))
            for idx in empty_indices:
                if idx not in covered and nodes[idx].value == ' ':
                    nodes[idx].value = 'O'
                    placed.append({'x': nodes[idx].x, 'y': nodes[idx].y, 'value': 'O', 'reason': f'{line_name}: remaining X quota ({rem_x}) consumed by required patterns'})

        disjoint_o = max_disjoint(reqs_o)
        if len(disjoint_o) == rem_o and rem_o > 0:
            covered = set().union(*(s for s, _ in disjoint_o))
            for idx in empty_indices:
                if idx not in covered and nodes[idx].value == ' ':
                    nodes[idx].value = 'X'
                    placed.append({'x': nodes[idx].x, 'y': nodes[idx].y, 'value': 'X', 'reason': f'{line_name}: remaining O quota ({rem_o}) consumed by required patterns'})

        return placed

    def deduce_line_combinations(self, nodes, max_pieces, line_name=''):
        vals = [n.value for n in nodes]
        empty_indices = [i for i, v in enumerate(vals) if v == ' ']
        if not empty_indices:
            return []

        cnt_x = vals.count('X')
        cnt_o = vals.count('O')
        rem_x = max_pieces - cnt_x
        rem_o = max_pieces - cnt_o
        if rem_x < 0 or rem_o < 0:
            return []

        if comb(len(empty_indices), rem_x) > 15000:
            return []

        valid_completions = []
        for x_pos in itertools.combinations(range(len(empty_indices)), rem_x):
            x_set = set(x_pos)
            cand = list(vals)
            for idx_i, cell_idx in enumerate(empty_indices):
                cand[cell_idx] = 'X' if idx_i in x_set else 'O'

            has_three = False
            for i in range(len(cand) - 2):
                if cand[i] == cand[i+1] == cand[i+2]:
                    has_three = True
                    break
            if not has_three:
                valid_completions.append(cand)

        if not valid_completions:
            return []

        placed = []
        for idx in empty_indices:
            val0 = valid_completions[0][idx]
            if all(comp[idx] == val0 for comp in valid_completions):
                if nodes[idx].value == ' ':
                    nodes[idx].value = val0
                    placed.append({'x': nodes[idx].x, 'y': nodes[idx].y, 'value': val0, 'reason': f'{line_name}: must be {val0} across all valid line completions'})

        return placed

    def step_deduce(self):
        # 1. Single-cell invalid move checks
        placed = []
        for y in range(self.height):
            for x in range(self.width):
                node = self.nodes[y][x]
                if node.value == ' ':
                    x_inv = self.is_invalid_move(node, 'X')
                    o_inv = self.is_invalid_move(node, 'O')
                    if x_inv and not o_inv:
                        node.value = 'O'
                        placed.append({'x': x, 'y': y, 'value': 'O', 'reason': 'Single-cell lookahead (X creates 3-in-a-row or exceeds quota)'})
                    elif o_inv and not x_inv:
                        node.value = 'X'
                        placed.append({'x': x, 'y': y, 'value': 'X', 'reason': 'Single-cell lookahead (O creates 3-in-a-row or exceeds quota)'})
        if placed:
            return placed

        # 2. Sequence and remaining quota pattern rules
        for y in range(self.height):
            row_nodes = [self.nodes[y][x] for x in range(self.width)]
            placed.extend(self.deduce_patterns_for_line(row_nodes, self.max_row, f'Row {y}'))
        for x in range(self.width):
            col_nodes = [self.nodes[y][x] for y in range(self.height)]
            placed.extend(self.deduce_patterns_for_line(col_nodes, self.max_col, f'Col {x}'))

        if placed:
            return placed

        # 3. Line completion intersection
        for y in range(self.height):
            row_nodes = [self.nodes[y][x] for x in range(self.width)]
            placed.extend(self.deduce_line_combinations(row_nodes, self.max_row, f'Row {y}'))
        for x in range(self.width):
            col_nodes = [self.nodes[y][x] for y in range(self.height)]
            placed.extend(self.deduce_line_combinations(col_nodes, self.max_col, f'Col {x}'))

        return placed

    def solve_full(self, timeout=2.0):
        total_placed = 0
        passes = 0
        while True:
            changes = self.step_deduce()
            if not changes:
                break
            total_placed += len(changes)
            passes += 1

        if self.is_solved():
            return {
                'solved': True,
                'placed': total_placed,
                'message': f'Puzzle fully solved! Placed {total_placed} cells across {passes} deduction passes.'
            }

        empty_count = sum(1 for y in range(self.height) for x in range(self.width) if self.nodes[y][x].value == ' ')

        # Only attempt backtracking if search space is small and bounded
        if empty_count <= 35 or (self.width * self.height <= 100):
            import time
            start_time = time.time()
            grid_matrix = [[self.nodes[y][x].value for x in range(self.width)] for y in range(self.height)]
            w, h = self.width, self.height
            max_r, max_c = self.max_row, self.max_col

            def is_valid_partial(g, r, c, val):
                if c >= 2 and g[r][c-1] == val and g[r][c-2] == val: return False
                if c <= w - 3 and g[r][c+1] == val and g[r][c+2] == val: return False
                if 0 < c < w - 1 and g[r][c-1] == val and g[r][c+1] == val: return False

                if r >= 2 and g[r-1][c] == val and g[r-2][c] == val: return False
                if r <= h - 3 and g[r+1][c] == val and g[r+2][c] == val: return False
                if 0 < r < h - 1 and g[r-1][c] == val and g[r+1][c] == val: return False

                rx = sum(1 for x in range(w) if (val if x == c else g[r][x]) == 'X')
                ro = sum(1 for x in range(w) if (val if x == c else g[r][x]) == 'O')
                if rx > max_r or ro > max_r: return False

                cx = sum(1 for y in range(h) if (val if y == r else g[y][c]) == 'X')
                co = sum(1 for y in range(h) if (val if y == r else g[y][c]) == 'O')
                if cx > max_c or co > max_c: return False

                return True

            def backtrack(r=0, c=0):
                if time.time() - start_time > timeout:
                    return False
                if r == h:
                    return True
                nr = r if c < w - 1 else r + 1
                nc = c + 1 if c < w - 1 else 0
                if grid_matrix[r][c] != ' ':
                    return backtrack(nr, nc)

                for cand in ('X', 'O'):
                    if is_valid_partial(grid_matrix, r, c, cand):
                        grid_matrix[r][c] = cand
                        if backtrack(nr, nc):
                            return True
                        grid_matrix[r][c] = ' '
                return False

            if backtrack(0, 0):
                for y in range(h):
                    for x in range(w):
                        self.nodes[y][x].value = grid_matrix[y][x]
                return {
                    'solved': True,
                    'placed': total_placed,
                    'message': f'Puzzle solved completely using deductions and search!'
                }

        return {
            'solved': False,
            'placed': total_placed,
            'message': f'Deductions complete: placed {total_placed} cells. {empty_count} cells remain (puzzle requires advanced lookahead or player guesses).'
        }

    def is_solved(self):
        for y in range(self.height):
            for x in range(self.width):
                if self.nodes[y][x].value == ' ':
                    return False
                if self.three_in_a_row(self.nodes[y][x]) or self.exceeds_max_pieces(self.nodes[y][x]):
                    return False
        return True

    def get_state(self):
        grid_data = []
        conflicts = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                node = self.nodes[y][x]
                is_clue = (self.initial_values[y][x] != -1)
                is_err = False
                if node.value in ('X', 'O'):
                    if self.three_in_a_row(node) or self.exceeds_max_pieces(node):
                        is_err = True
                        conflicts.append({'x': x, 'y': y})
                row.append({
                    'value': node.value,
                    'is_clue': is_clue,
                    'is_error': is_err
                })
            grid_data.append(row)

        row_counts = []
        for y in range(self.height):
            rx = sum(1 for x in range(self.width) if self.nodes[y][x].value == 'X')
            ro = sum(1 for x in range(self.width) if self.nodes[y][x].value == 'O')
            row_counts.append({'x': rx, 'o': ro, 'target': self.max_row, 'complete': (rx == self.max_row and ro == self.max_row)})

        col_counts = []
        for x in range(self.width):
            cx = sum(1 for y in range(self.height) if self.nodes[y][x].value == 'X')
            co = sum(1 for y in range(self.height) if self.nodes[y][x].value == 'O')
            col_counts.append({'x': cx, 'o': co, 'target': self.max_col, 'complete': (cx == self.max_col and co == self.max_col)})

        empty_count = sum(1 for y in range(self.height) for x in range(self.width) if self.nodes[y][x].value == ' ')

        return {
            'width': self.width,
            'height': self.height,
            'max_row': self.max_row,
            'max_col': self.max_col,
            'board_name': self.board_name,
            'grid': grid_data,
            'row_counts': row_counts,
            'col_counts': col_counts,
            'conflicts': conflicts,
            'empty_count': empty_count,
            'is_solved': self.is_solved()
        }

game_state = GameState()

INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Binairo Puzzle Solver & Player</title>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --panel-border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --cell-bg: #334155;
      --cell-clue-bg: #1e293b;
      --cell-border: #475569;
      --color-x: #38bdf8;
      --color-o: #f59e0b;
      --color-err: #ef4444;
      --color-success: #10b981;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }

    header {
      background: var(--card-bg);
      border-bottom: 1px solid var(--panel-border);
      padding: 12px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
    }

    header h1 {
      font-size: 1.25rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .badge {
      background: #0284c7;
      color: #fff;
      font-size: 0.75rem;
      padding: 3px 8px;
      border-radius: 999px;
      font-weight: 600;
    }

    .controls {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }

    button, label.btn {
      background: var(--panel-border);
      color: var(--text);
      border: 1px solid #475569;
      padding: 7px 14px;
      border-radius: 6px;
      font-size: 0.85rem;
      font-weight: 500;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
      user-select: none;
    }

    button:hover, label.btn:hover {
      background: #475569;
      border-color: #64748b;
    }

    button.primary {
      background: #0284c7;
      border-color: #38bdf8;
      color: #fff;
    }
    button.primary:hover {
      background: #0369a1;
    }

    button.success {
      background: #059669;
      border-color: #10b981;
      color: #fff;
    }
    button.success:hover {
      background: #047857;
    }

    button.danger {
      background: #b91c1c;
      border-color: #ef4444;
      color: #fff;
    }

    .status-bar {
      background: #1e293b;
      border-bottom: 1px solid var(--panel-border);
      padding: 8px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 0.85rem;
      color: var(--text-muted);
    }

    .status-bar strong {
      color: var(--text);
    }

    .status-badge {
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 0.75rem;
      font-weight: 600;
    }
    .status-badge.in-progress { background: #ca8a04; color: #fff; }
    .status-badge.solved { background: #16a34a; color: #fff; }
    .status-badge.conflict { background: #dc2626; color: #fff; }

    main {
      flex: 1;
      display: flex;
      overflow: hidden;
      position: relative;
    }

    .board-container {
      flex: 1;
      overflow: auto;
      padding: 24px;
      display: flex;
      justify-content: center;
      align-items: flex-start;
    }

    .grid-wrapper {
      background: var(--card-bg);
      padding: 16px;
      border-radius: 12px;
      border: 1px solid var(--panel-border);
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
      display: inline-block;
      user-select: none;
    }

    .binairo-table {
      border-collapse: separate;
      border-spacing: 2px;
    }

    .binairo-table th {
      font-size: 0.65rem;
      color: var(--text-muted);
      padding: 2px 4px;
      font-weight: 600;
      text-align: center;
      white-space: nowrap;
    }

    .binairo-table th.satisfied {
      color: var(--color-success);
    }

    .cell {
      width: 26px;
      height: 26px;
      min-width: 26px;
      min-height: 26px;
      border-radius: 4px;
      background: var(--cell-bg);
      border: 1px solid var(--cell-border);
      font-size: 0.9rem;
      font-weight: 700;
      text-align: center;
      line-height: 24px;
      cursor: pointer;
      transition: background 0.1s, transform 0.05s;
    }

    .cell:hover {
      filter: brightness(1.2);
    }

    .cell:active {
      transform: scale(0.92);
    }

    .cell.clue {
      background: var(--cell-clue-bg);
      border-color: #64748b;
      cursor: default;
    }

    .cell.val-X {
      color: var(--color-x);
    }

    .cell.val-O {
      color: var(--color-o);
    }

    .cell.clue.val-X {
      color: #93c5fd;
      font-weight: 900;
    }

    .cell.clue.val-O {
      color: #fde047;
      font-weight: 900;
    }

    .cell.error {
      background: #7f1d1d !important;
      border-color: var(--color-err) !important;
      animation: shake 0.3s ease;
    }

    .cell.highlight-new {
      animation: pulse 1s ease;
    }

    @keyframes pulse {
      0% { transform: scale(1.3); background: #065f46; }
      100% { transform: scale(1); }
    }

    /* Modal for importing HTML */
    .modal {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.75);
      z-index: 1000;
      justify-content: center;
      align-items: center;
      padding: 16px;
    }

    .modal.active { display: flex; }

    .modal-content {
      background: var(--card-bg);
      border: 1px solid var(--panel-border);
      border-radius: 12px;
      width: 100%;
      max-width: 600px;
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .modal-content textarea {
      width: 100%;
      height: 200px;
      background: #0f172a;
      color: var(--text);
      border: 1px solid var(--panel-border);
      border-radius: 6px;
      padding: 12px;
      font-family: monospace;
      font-size: 0.8rem;
      resize: vertical;
    }
  </style>
</head>
<body>

  <header>
    <h1>
      <span>Binairo</span>
      <span class="badge" id="boardSizeBadge">Loading...</span>
    </h1>

    <div class="controls">
      <button class="primary" id="btnStep" title="Apply 1 deduction pass">⚡ Step Deduce</button>
      <button class="success" id="btnPlay" title="Auto-step with visual animation">▶ Play</button>
      <button class="success" id="btnSolve" title="Apply all deductions immediately">⚡ Deduce All</button>
      <button id="btnReset" title="Reset back to initial clues">↺ Reset</button>
      <button id="btnLoadDefault" title="Load sample 10x10 puzzle">10×10 Preset</button>
      <button id="btnImportHtml">📥 Import HTML</button>
    </div>
  </header>

  <div class="status-bar">
    <div>
      Puzzle: <strong id="boardName">--</strong> &nbsp;|&nbsp;
      Empty Cells: <strong id="emptyCount">--</strong>
    </div>
    <div style="display:flex; align-items:center; gap:12px;">
      <div id="toastMessage" style="display:none; padding:3px 10px; border-radius:4px; font-size:0.8rem; background:#065f46; color:#fff; font-weight:500;"></div>
      <span class="status-badge in-progress" id="statusBadge">Playing</span>
    </div>
  </div>

  <main>
    <div class="board-container">
      <div class="grid-wrapper" id="gridWrapper">
        <table class="binairo-table" id="binairoTable"></table>
      </div>
    </div>
  </main>

  <div class="modal" id="importModal">
    <div class="modal-content">
      <h2>Import Board from Webpage HTML</h2>
      <p style="font-size: 0.85rem; color: var(--text-muted);">
        Paste the HTML snippet of the board (e.g. from <code>board.txt</code> or browser DevTools) below:
      </p>
      <textarea id="htmlInput" placeholder="<div class='board-back'>...</div>"></textarea>
      <div style="display:flex; justify-content:flex-end; gap:8px;">
        <button id="btnCancelImport">Cancel</button>
        <button class="primary" id="btnSubmitImport">Import Grid</button>
      </div>
    </div>
  </div>

  <script>
    let state = null;
    let autoSolving = false;

    async function fetchState() {
      try {
        const res = await fetch('/api/board');
        if (!res.ok) throw new Error("HTTP " + res.status);
        state = await res.json();
        render();
      } catch (err) {
        console.warn("fetchState waiting for server:", err.message);
        const wrapper = document.getElementById('gridWrapper');
        if (wrapper && !state) {
          wrapper.innerHTML = `
            <div style="padding: 30px; text-align: center; color: #f87171;">
              <h3 style="margin-bottom: 8px;">Connecting to Binairo Server...</h3>
              <p style="color: #94a3b8; font-size: 0.85rem; max-width: 400px; margin: 0 auto;">
                Make sure <code>python3 app.py</code> is running in your terminal.<br>
                <em>(Do not press Ctrl+Z to leave terminal; use Ctrl+C to stop)</em>
              </p>
              <button onclick="fetchState()" class="primary" style="margin-top: 14px;">🔄 Retry Now</button>
            </div>
          `;
        }
        setTimeout(fetchState, 1500);
      }
    }

    function render(newlyPlaced = []) {
      if (!state) return;

      const wrapper = document.getElementById('gridWrapper');
      let table = document.getElementById('binairoTable');
      if (!table) {
        wrapper.innerHTML = '<table class="binairo-table" id="binairoTable"></table>';
        table = document.getElementById('binairoTable');
      }

      document.getElementById('boardSizeBadge').textContent = `${state.width} × ${state.height}`;
      document.getElementById('boardName').textContent = state.board_name;
      document.getElementById('emptyCount').textContent = state.empty_count;

      const badge = document.getElementById('statusBadge');
      if (state.is_solved) {
        badge.className = 'status-badge solved';
        badge.textContent = '🎉 Solved!';
      } else if (state.conflicts.length > 0) {
        badge.className = 'status-badge conflict';
        badge.textContent = `⚠ ${state.conflicts.length} Violations`;
      } else {
        badge.className = 'status-badge in-progress';
        badge.textContent = 'In Progress';
      }

      table.innerHTML = '';

      // Column header counters
      const thead = document.createElement('tr');
      const cornerTh = document.createElement('th');
      cornerTh.textContent = 'y \\ x';
      thead.appendChild(cornerTh);

      for (let x = 0; x < state.width; x++) {
        const colInfo = state.col_counts[x];
        const th = document.createElement('th');
        th.innerHTML = `X:${colInfo.x}<br>O:${colInfo.o}`;
        if (colInfo.complete) th.classList.add('satisfied');
        thead.appendChild(th);
      }
      table.appendChild(thead);

      // Rows
      for (let y = 0; y < state.height; y++) {
        const tr = document.createElement('tr');

        // Row header counter
        const rowInfo = state.row_counts[y];
        const rowTh = document.createElement('th');
        rowTh.innerHTML = `X:${rowInfo.x} O:${rowInfo.o}`;
        if (rowInfo.complete) rowTh.classList.add('satisfied');
        tr.appendChild(rowTh);

        // Cells
        for (let x = 0; x < state.width; x++) {
          const cellData = state.grid[y][x];
          const td = document.createElement('td');
          td.className = 'cell';

          if (cellData.is_clue) td.classList.add('clue');
          if (cellData.is_error) td.classList.add('error');
          if (cellData.value === 'X') td.classList.add('val-X');
          if (cellData.value === 'O') td.classList.add('val-O');

          td.textContent = cellData.value !== ' ' ? cellData.value : '';

          if (!cellData.is_clue) {
            td.addEventListener('click', () => cycleCell(x, y, 1));
            td.addEventListener('contextmenu', (e) => {
              e.preventDefault();
              cycleCell(x, y, -1);
            });
          }

          if (newlyPlaced && newlyPlaced.some(p => p.x === x && p.y === y)) {
            td.classList.add('highlight-new');
          }

          tr.appendChild(td);
        }
        table.appendChild(tr);
      }
    }

    let playInterval = null;

    function showToast(msg, isSuccess = true) {
      const toast = document.getElementById('toastMessage');
      toast.textContent = msg;
      toast.style.background = isSuccess ? '#065f46' : '#991b1b';
      toast.style.display = 'block';
      setTimeout(() => { toast.style.display = 'none'; }, 4000);
    }

    async function cycleCell(x, y, dir = 1) {
      const cell = state.grid[y][x];
      const cycle = [' ', 'X', 'O'];
      let idx = cycle.indexOf(cell.value);
      idx = (idx + dir + cycle.length) % cycle.length;
      const nextVal = cycle[idx];

      const res = await fetch('/api/set_cell', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ x, y, value: nextVal })
      });
      state = await res.json();
      render();
    }

    async function performStep(showAlert = false) {
      const res = await fetch('/api/step', { method: 'POST' });
      const data = await res.json();
      state = data.state;
      render(data.placed);
      if (data.placed.length === 0) {
        if (showAlert) showToast("No further deductions can be made.", false);
        return false;
      } else {
        const sampleReason = data.placed[0].reason ? ` [${data.placed[0].reason}]` : '';
        showToast(`Deduction pass placed ${data.placed.length} cell(s)${sampleReason}`);
        return true;
      }
    }

    document.getElementById('btnStep').addEventListener('click', () => performStep(true));

    document.getElementById('btnPlay').addEventListener('click', () => {
      const btn = document.getElementById('btnPlay');
      if (playInterval) {
        clearInterval(playInterval);
        playInterval = null;
        btn.textContent = '▶ Play';
        btn.classList.remove('danger');
        btn.classList.add('success');
      } else {
        btn.textContent = '⏸ Pause';
        btn.classList.remove('success');
        btn.classList.add('danger');
        playInterval = setInterval(async () => {
          const continued = await performStep(false);
          if (!continued || state.is_solved) {
            clearInterval(playInterval);
            playInterval = null;
            btn.textContent = '▶ Play';
            btn.classList.remove('danger');
            btn.classList.add('success');
            if (state.is_solved) {
              showToast("🎉 Puzzle solved completely!");
            }
          }
        }, 220);
      }
    });

    document.getElementById('btnSolve').addEventListener('click', async () => {
      const btn = document.getElementById('btnSolve');
      btn.disabled = true;
      btn.textContent = 'Solving...';
      try {
        const res = await fetch('/api/solve_all', { method: 'POST' });
        const data = await res.json();
        state = data.state;
        render();
        if (data.result && data.result.message) {
          showToast(data.result.message, data.result.solved);
        }
      } catch (err) {
        showToast('Error: ' + err.message, false);
      } finally {
        btn.disabled = false;
        btn.textContent = '⚡ Deduce All';
      }
    });

    document.getElementById('btnReset').addEventListener('click', async () => {
      if (playInterval) {
        clearInterval(playInterval);
        playInterval = null;
        const playBtn = document.getElementById('btnPlay');
        playBtn.textContent = '▶ Play';
        playBtn.classList.remove('danger');
        playBtn.classList.add('success');
      }
      const res = await fetch('/api/reset', { method: 'POST' });
      state = await res.json();
      render();
    });

    document.getElementById('btnLoadDefault').addEventListener('click', async () => {
      const res = await fetch('/api/load_default', { method: 'POST' });
      state = await res.json();
      render();
    });

    // Import modal
    const modal = document.getElementById('importModal');
    document.getElementById('btnImportHtml').addEventListener('click', () => modal.classList.add('active'));
    document.getElementById('btnCancelImport').addEventListener('click', () => modal.classList.remove('active'));

    document.getElementById('btnSubmitImport').addEventListener('click', async () => {
      const html = document.getElementById('htmlInput').value;
      if (!html.trim()) return;
      const res = await fetch('/api/load_html', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ html })
      });
      const data = await res.json();
      if (data.success) {
        state = data.state;
        render();
        modal.classList.remove('active');
        document.getElementById('htmlInput').value = '';
      } else {
        alert(data.message);
      }
    });

    fetchState();
  </script>
</body>
</html>
"""

class AppHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ('/', '/index.html'):
            body = INDEX_HTML.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif url.path == '/api/board':
            self._send_json(game_state.get_state())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        url = urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
        payload = json.loads(post_data.decode('utf-8')) if post_data else {}

        if url.path == '/api/step':
            placed = game_state.step_deduce()
            self._send_json({'placed': placed, 'state': game_state.get_state()})

        elif url.path == '/api/solve_all':
            result = game_state.solve_full()
            self._send_json({'result': result, 'state': game_state.get_state()})

        elif url.path == '/api/reset':
            game_state.reset()
            self._send_json(game_state.get_state())

        elif url.path == '/api/load_default':
            game_state.initial_values = [row[:] for row in DEFAULT_10x10]
            game_state.width = 10
            game_state.height = 10
            game_state.max_row = 5
            game_state.max_col = 5
            game_state.board_name = "Default 10x10"
            game_state.reset()
            self._send_json(game_state.get_state())

        elif url.path == '/api/load_html':
            html_text = payload.get('html', '')
            success, msg = game_state.load_from_html_string(html_text)
            self._send_json({'success': success, 'message': msg, 'state': game_state.get_state()})

        elif url.path == '/api/set_cell':
            x = payload.get('x')
            y = payload.get('y')
            val = payload.get('value', ' ')
            if 0 <= y < game_state.height and 0 <= x < game_state.width:
                if game_state.initial_values[y][x] == -1:  # Not a clue
                    game_state.nodes[y][x].value = val
            self._send_json(game_state.get_state())

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Quiet server logs
        return

class ReusableHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

def run_server(start_port=8080):
    port = start_port
    server = None
    while port < start_port + 20:
        try:
            server = ReusableHTTPServer(('127.0.0.1', port), AppHandler)
            break
        except OSError as e:
            if e.errno == 98:  # Address already in use
                port += 1
            else:
                raise

    if server is None:
        print(f"Error: Could not find an open port starting from {start_port}.")
        sys.exit(1)

    url = f"http://localhost:{port}"
    print(f"==================================================")
    print(f" Binairo Application is running at:")
    print(f" {url}")
    print(f" (Press Ctrl+C to stop the application)")
    print(f"==================================================")

    # Open the browser automatically
    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.server_close()

if __name__ == '__main__':
    port = 8080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run_server(port)

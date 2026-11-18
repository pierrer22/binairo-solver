import itertools
import os
import re
from math import comb
from time import sleep


def load_grid_from_html(filepath, clues_only=True):
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()

    pattern = re.compile(
        r'<div[^>]*style=\"[^\"]*top:\s*(\d+)px;\s*left:\s*(\d+)px;[^\"]*\"[^>]*class=\"([^\"]*(?:cell-off|cell-0|cell-1)[^\"]*)\"',
        re.IGNORECASE
    )
    matches = pattern.findall(html)
    if not matches:
        pattern = re.compile(
            r'<div[^>]*class=\"([^\"]*(?:cell-off|cell-0|cell-1)[^\"]*)\"[^>]*style=\"[^\"]*top:\s*(\d+)px;\s*left:\s*(\d+)px;[^\"]*\"',
            re.IGNORECASE
        )
        matches = [(m[1], m[2], m[0]) for m in pattern.findall(html)]

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

        if clues_only and 'task-cell' not in cls:
            continue

        if 'cell-1' in cls:
            grid_values[y][x] = 1
        elif 'cell-0' in cls:
            grid_values[y][x] = 0

    return grid_values, width, height


board_file = "board.txt"
if os.path.exists(board_file):
    grid_values, WIDTH, HEIGHT = load_grid_from_html(board_file)
else:
    WIDTH = 10
    HEIGHT = 10
    grid_values = [
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

MAX_ROW = WIDTH // 2
MAX_COLUMN = HEIGHT // 2

class Node:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.value = None
        # neighbors
        self.north = None
        self.south = None
        self.east = None
        self.west = None

grid = [[Node(x, y) for x in range(WIDTH)] for y in range(HEIGHT)]

# assign values to the grid nodes
for y in range(HEIGHT):
    for x in range(WIDTH):
        # -1 = empty, 0 = white circle, 1 = black circle
        if grid_values[y][x] == -1:
            grid[y][x].value = ' '
        elif grid_values[y][x] == 0:
            grid[y][x].value = 'O'
        elif grid_values[y][x] == 1:
            grid[y][x].value = 'X'
        
# set neighbors for each node
for y in range(HEIGHT):
    for x in range(WIDTH):
        if y > 0:
            grid[y][x].north = grid[y-1][x]
        if y < HEIGHT - 1:
            grid[y][x].south = grid[y+1][x]
        if x > 0:
            grid[y][x].west = grid[y][x-1]
        if x < WIDTH - 1:
            grid[y][x].east = grid[y][x+1]

# count the number of 'X' and 'O' pieces in the grid for that node's row and column separately
def count_pieces(node):
    row_x = 1 if node.value == 'X' else 0
    row_o = 1 if node.value == 'O' else 0
    col_x = row_x
    col_o = row_o

    # count pieces in the row
    current = node.west
    while current is not None:
        if current.value == 'X':
            row_x += 1
        elif current.value == 'O':
            row_o += 1
        current = current.west
    current = node.east
    while current is not None:
        if current.value == 'X':
            row_x += 1
        elif current.value == 'O':
            row_o += 1
        current = current.east

    # count pieces in the column
    current = node.north
    while current is not None:
        if current.value == 'X':
            col_x += 1
        elif current.value == 'O':
            col_o += 1
        current = current.north
    current = node.south
    while current is not None:
        if current.value == 'X':
            col_x += 1
        elif current.value == 'O':
            col_o += 1
        current = current.south

    return (row_x, row_o), (col_x, col_o)

# set rules for the game
def check_win(grid):
    # win if no more empty values in the grid and no rules violated
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if grid[y][x].value == ' ':
                return False
            if three_in_a_row(grid[y][x]) or exceeds_max_pieces(grid[y][x]):
                return False
    return True

def three_in_a_row(node):
    if node.value not in ('X', 'O'):
        return False

    # check if placing a piece in this node would create three in a row
    # check horizontal
    count = 1
    current = node.west
    while current is not None and current.value == node.value:
        count += 1
        current = current.west
    current = node.east
    while current is not None and current.value == node.value:
        count += 1
        current = current.east
    if count >= 3:
        return True
    
    # check vertical
    count = 1
    current = node.north
    while current is not None and current.value == node.value:
        count += 1
        current = current.north
    current = node.south
    while current is not None and current.value == node.value:
        count += 1
        current = current.south
    if count >= 3:
        return True

    return False

# check if placing a piece in this node would exceed the maximum number of pieces per row or column
def exceeds_max_pieces(node):
    (row_x, row_o), (col_x, col_o) = count_pieces(node)
    if row_x > MAX_ROW or row_o > MAX_ROW or col_x > MAX_COLUMN or col_o > MAX_COLUMN:
        return True
    return False

def is_invalid_move(node, value):
    original_value = node.value
    node.value = value
    invalid = three_in_a_row(node) or exceeds_max_pieces(node)
    node.value = original_value
    return invalid

# draw the grid
def draw(grid):
    for y in range(HEIGHT):
        for x in range(WIDTH):
            print(grid[y][x].value, end=' ')
        print()

# loop through the grid and check for invalid moves by placing a 'X' or 'O' in each empty node
def check_invalid_moves(grid):
    changed = False
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if grid[y][x].value == ' ':
                x_invalid = is_invalid_move(grid[y][x], 'X')
                o_invalid = is_invalid_move(grid[y][x], 'O')
                if x_invalid and not o_invalid:
                    grid[y][x].value = 'O'
                    print(f'O placed at ({x}, {y}) [Single-cell lookahead]')
                    changed = True
                elif o_invalid and not x_invalid:
                    grid[y][x].value = 'X'
                    print(f'X placed at ({x}, {y}) [Single-cell lookahead]')
                    changed = True
    return changed

# Deduce using sequence and quota rules:
# - Three consecutive blank nodes must contain at least one X and O
# - A X--X sequence must contain at least one O
# - A O--O sequence must contain at least one X
# - A X--O or O--X sequence must contain at least one O and X
# - Disjoint pattern requirements consuming remaining line quota force other blanks to opposite piece
def deduce_patterns_for_line(nodes, max_pieces, line_name=''):
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
        if not req_list:
            return ()
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
    # If disjoint requirements for X consume all remaining allowed X's in the line:
    disjoint_x = max_disjoint(reqs_x)
    if len(disjoint_x) == rem_x and rem_x > 0:
        covered = set().union(*(s for s, _ in disjoint_x))
        for idx in empty_indices:
            if idx not in covered and nodes[idx].value == ' ':
                nodes[idx].value = 'O'
                placed.append((nodes[idx], 'O', f'{line_name}: remaining X quota ({rem_x}) consumed by required patterns'))

    # If disjoint requirements for O consume all remaining allowed O's in the line:
    disjoint_o = max_disjoint(reqs_o)
    if len(disjoint_o) == rem_o and rem_o > 0:
        covered = set().union(*(s for s, _ in disjoint_o))
        for idx in empty_indices:
            if idx not in covered and nodes[idx].value == ' ':
                nodes[idx].value = 'X'
                placed.append((nodes[idx], 'X', f'{line_name}: remaining O quota ({rem_o}) consumed by required patterns'))

    return placed

# Deduces pieces where all valid line completions with remaining quotas agree
def deduce_line_combinations(nodes, max_pieces, line_name=''):
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
                placed.append((nodes[idx], val0, f'{line_name}: cell must be {val0} in all valid line completions'))

    return placed

def check_all_deductions(grid):
    # 1. Try single-cell invalid move checks first
    if check_invalid_moves(grid):
        return True

    # 2. Check pattern quota rules across all rows
    pattern_placed = 0
    for y in range(HEIGHT):
        row_nodes = [grid[y][x] for x in range(WIDTH)]
        for node, val, reason in deduce_patterns_for_line(row_nodes, MAX_ROW, f'Row {y}'):
            print(f'{val} placed at ({node.x}, {node.y}) [{reason}]')
            pattern_placed += 1

    # Check pattern quota rules across all columns
    for x in range(WIDTH):
        col_nodes = [grid[y][x] for y in range(HEIGHT)]
        for node, val, reason in deduce_patterns_for_line(col_nodes, MAX_COLUMN, f'Col {x}'):
            print(f'{val} placed at ({node.x}, {node.y}) [{reason}]')
            pattern_placed += 1

    if pattern_placed > 0:
        return True

    # 3. Check line completion consistency across rows and columns
    comb_placed = 0
    for y in range(HEIGHT):
        row_nodes = [grid[y][x] for x in range(WIDTH)]
        for node, val, reason in deduce_line_combinations(row_nodes, MAX_ROW, f'Row {y}'):
            print(f'{val} placed at ({node.x}, {node.y}) [{reason}]')
            comb_placed += 1

    for x in range(WIDTH):
        col_nodes = [grid[y][x] for y in range(HEIGHT)]
        for node, val, reason in deduce_line_combinations(col_nodes, MAX_COLUMN, f'Col {x}'):
            print(f'{val} placed at ({node.x}, {node.y}) [{reason}]')
            comb_placed += 1

    return comb_placed > 0

if __name__ == '__main__':
    clue_count = sum(1 for row in grid_values for v in row if v != -1)
    print(f"Loaded {WIDTH}x{HEIGHT} puzzle with {clue_count} initial clues.\n")

    # main game loop while deductions can be made
    pass_num = 0
    while not check_win(grid):
        pass_num += 1
        print(f"--- Deduction Pass {pass_num} ---")
        changed = check_all_deductions(grid)
        if not changed:
            print("No more deductions can be made.")
            break
        sleep(0.5)

    draw(grid)
    if check_win(grid):
        print("\n🎉 Puzzle solved completely!")
    else:
        empty = sum(1 for y in range(HEIGHT) for x in range(WIDTH) if grid[y][x].value == ' ')
        print(f"\nFinished deduction passes. {empty} empty cells remain.")

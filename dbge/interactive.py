import ast
import curses
import sys


def traverse_ast(node):
    yield node
    for child in ast.iter_child_nodes(node):
        yield from traverse_ast(child)


def _traverse_ast(node):
    for child in ast.iter_child_nodes(node):
        yield from _traverse_ast(child)
    yield node


def draw_tree(stdscr, node, selected=None, indent=0):
    # Set the colors
    if selected is None:
        stdscr.attron(curses.color_pair(1))
    elif node is selected:
        stdscr.attron(curses.color_pair(2))
    else:
        stdscr.attron(curses.color_pair(1))

    shift = node.lineno

    # Draw the node
    if hasattr(node, "lineno"):
        stdscr.addstr(node.lineno - shift, node.col_offset - indent, ast.unparse(node))
    else:
        stdscr.addstr(0, 0, ast.unparse(node))

    stdscr.attron(curses.color_pair(2))
    stdscr.addstr(selected.lineno - shift, selected.col_offset - indent, ast.unparse(selected))

    # Reset the colors
    stdscr.attroff(curses.color_pair(1))
    stdscr.attroff(curses.color_pair(2))


def draw_node(stdscr, node):
    stdscr.addstr(0, 0, repr(node))
    stdscr.addstr(1, 0, ast.unparse(node))


def _display(stdscr, a2b):
    # Set up the colors
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_WHITE, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)

    # Set up the tree and node window
    tree_win = stdscr.subwin(curses.LINES, curses.COLS // 2, 0, 0)
    node_win = stdscr.subwin(curses.LINES, curses.COLS // 2, 0, curses.COLS // 2)

    # Gets the ast from the AST2Bytecode instance
    tree = a2b.ast

    # Initialize the selected node
    # selected_node = tree
    all_nodes = list(x for x in _traverse_ast(tree) if len(getattr(x, 'insts', [])) > 0)
    # all_nodes = list(x for x in a2b.flat_ast if len(x.insts) > 0)
    index = 0
    limit = len(all_nodes)

    # Draw the AST
    node = all_nodes[index]
    draw_tree(tree_win, tree, selected=node, indent=a2b.indent)
    draw_node(node_win, node)

    while True:
        key = stdscr.getch()
        if key in (curses.KEY_LEFT, curses.KEY_RIGHT):
            incr = 1 if key == curses.KEY_RIGHT else -1
            index = (index + incr) % limit
        # elif key in (curses.KEY_DOWN, curses.KEY_UP):
            # incr = 1 if key == curses.KEY_DOWN else -1
            # for i, node in enumerate(all_nodes, start=(index + incr) % limit):
            #     if isinstance(node, ast.stmt):
            #         index = i
            #         break
            # else:
            #     index = (index + incr) % limit
        elif key == ord("q"):
            return None, None
        elif key in (curses.KEY_ENTER, 10, 13):
            node = all_nodes[index]
            return node, node.insts[0]

        # Redraw the AST
        stdscr.clear()
        node = all_nodes[index]
        draw_tree(tree_win, tree, selected=node, indent=a2b.indent)
        draw_node(node_win, node)
        stdscr.refresh()


def select_astnode(a2b):
    return curses.wrapper(_display, a2b)

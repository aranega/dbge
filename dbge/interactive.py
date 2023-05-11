import ast
import curses
import inspect
import sys


def traverse_ast(node):
    yield node
    for child in ast.iter_child_nodes(node):
        yield from traverse_ast(child)


def _traverse_ast(node):
    for child in ast.iter_child_nodes(node):
        yield from _traverse_ast(child)
    yield node


def display_code(stdscr, code_str, line_shift, selected=None, indent=0):
    # Set the colors
    stdscr.attron(curses.color_pair(1))

    # Draw the node
    stdscr.addstr(0, 0, code_str)

    # Draw the selection
    stdscr.attron(curses.color_pair(2))
    stdscr.addstr(selected.lineno - line_shift, selected.col_offset - indent, ast.unparse(selected))

    # Reset the colors
    stdscr.attroff(curses.color_pair(1))
    stdscr.attroff(curses.color_pair(2))


def display_node_info(stdscr, node):
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
    src_code = inspect.getsource(a2b.codeobj)
    display_code(tree_win, src_code, selected=node, indent=a2b.indent, line_shift=tree.lineno)
    display_node_info(node_win, node)

    while True:
        key = stdscr.getch()
        if key in (curses.KEY_LEFT, curses.KEY_RIGHT):
            incr = 1 if key == curses.KEY_RIGHT else -1
            index = (index + incr) % limit
        elif key == curses.KEY_DOWN:
            current_line = all_nodes[index].lineno
            for i, node in enumerate(all_nodes):
                if node.lineno > current_line:
                    index = i
                    break
            else:
                index = (index + 1) % limit
        elif key == curses.KEY_UP:
            current_line = all_nodes[index].lineno
            for i, node in reversed(list(enumerate(all_nodes))):
                if node.lineno < current_line:
                    index = i
                    break
            else:
                index = (index - 1) % limit
        elif key == ord("q"):
            return None, None
        elif key in (curses.KEY_ENTER, 10, 13):
            node = all_nodes[index]
            inst = node.insts[0]
            return node, inst, inst.mapper

        # Redraw the AST
        stdscr.clear()
        node = all_nodes[index]
        display_code(tree_win, src_code, selected=node, indent=a2b.indent, line_shift=tree.lineno)
        display_node_info(node_win, node)
        stdscr.refresh()


def select_astnode(a2b):
    return curses.wrapper(_display, a2b)

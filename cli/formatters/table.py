"""
Table formatter for Dockyard CLI
"""
from typing import List


def format_table(headers: List[str], rows: List[List[str]], min_width: int = 10) -> str:
    """Format data as a table

    Args:
        headers: List of column headers
        rows: List of rows (each row is a list of strings)
        min_width: Minimum column width

    Returns:
        Formatted table string
    """
    if not headers or not rows:
        return ""

    # Calculate column widths
    col_widths = [max(len(h), min_width) for h in headers]

    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    # Build header
    header_line = " ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    separator = "-" * len(header_line)

    # Build rows
    table_rows = []
    for row in rows:
        table_row = " ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
        table_rows.append(table_row)

    # Combine
    table = [header_line, separator] + table_rows

    return "\n".join(table)


def print_table(headers: List[str], rows: List[List[str]], min_width: int = 10):
    """Print formatted table

    Args:
        headers: List of column headers
        rows: List of rows (each row is a list of strings)
        min_width: Minimum column width
    """
    table = format_table(headers, rows, min_width)
    if table:
        print(table)

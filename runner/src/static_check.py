import ast

FORBIDDEN_MODULES = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "shutil",
    "pathlib",          # high-level file access
    "fcntl",            # low-level fs control (Unix)
    "signal",           # sending kill signals
    "resource",         # limit bypass
    "ctypes",           # raw C interop → sandbox escape
    "multiprocessing",  # spawns new processes
    "threading",        # background tasks
    "asyncio",          # can schedule infinite loops
    "selectors",        # advanced socket operations
    "urllib", "http",   # external network comms
    "inspect",          # can access caller frame
    "importlib",        # dynamic imports / loader editing
}

FORBIDDEN_FUNCTIONS = {
    "eval",
    "exec",
    "__import__",
    "compile",
    "open",            # file access
    "input",           # real input hijacking
    "globals", "locals",   # can inspect and manipulate env
    "vars",                # reflection
    "getattr", "setattr",  # dynamic runtime access
    "delattr",
    "dir",                # can explore objects
}

FORBIDDEN_ATTRS = {"__class__", "__dict__", "__bases__", "__mro__", "__subclasses__"}

def ast_static_check(code: str):
    found = []

    try:
        tree = ast.parse(code)
    except SyntaxError:
        found.append("syntax error")
        return found

    for node in ast.walk(tree):

        # Forbidden import modules
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_MODULES:
                    found.append(f"import {alias.name}")

        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in FORBIDDEN_MODULES:
                found.append(f"from {node.module} import ...")

        # Forbidden function calls
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in FORBIDDEN_FUNCTIONS:
                    found.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr in FORBIDDEN_FUNCTIONS:
                    found.append(node.func.attr)

        # Forbidden attributes (sandbox breakouts)
        if isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_ATTRS:
                found.append(f"attribute {node.attr}")

        # Block with-statements (usually file access)
        if isinstance(node, ast.With):
            found.append("with statement")

    return found


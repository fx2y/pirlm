PROGRAM = [
    {"tool": "echo", "args": {"text": "alpha"}},
    {"tool": "readfile", "args": {"path": "tests/fixtures/sample.txt"}},
    {"tool": "bash", "args": {"command": "printf shell_ok"}},
]

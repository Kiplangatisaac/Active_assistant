import re

with open(r"src\active_assistant\ui\main_window.py", "r") as f:
    content = f.read()

# Fix the double self issue
content = content.replace("self.self.theme[", "self.theme[")

with open(r"src\active_assistant\ui\main_window.py", "w") as f:
    f.write(content)

print("Done")
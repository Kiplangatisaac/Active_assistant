import re

with open(r"src\active_assistant\ui\main_window.py", "r") as f:
    content = f.read()

content = re.sub(r'\btheme\["', 'self.theme["', content)

with open(r"src\active_assistant\ui\main_window.py", "w") as f:
    f.write(content)

print("Done")
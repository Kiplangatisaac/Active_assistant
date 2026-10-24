import re

with open(r'src\active_assistant\ui\main_window.py', 'r') as f:
    content = f.read()

with open(r'chat_upload.py', 'r') as f:
    new_impl = f.read()

# Find the _send_chat method and insert new methods before it
old_send_chat = '''def _send_chat(self):
        """Send chat message."""
        text = self.chat_input.get("1.0", "end-1c").strip()
        if not text:
            return
        
        self.chat_input.delete("1.0", "end")
        
        # Add user message
        self._add_chat_message("user", text)
        
        # Process asynchronously
        self._run_async(self._process_chat(text))'''

# Insert new methods before _send_chat
new_methods = new_impl + '\n\n'

# Replace - insert new methods before the old _send_chat
content = content.replace(old_send_chat, new_methods + old_send_chat)

with open(r'src\active_assistant\ui\main_window.py', 'w') as f:
    f.write(content)

print('Done')
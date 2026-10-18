import re
file = "/home/mboyle/bin/bd-fleet-bench"
with open(file, "r") as f:
    content = f.read()

# First, remove the invalid '--autocompact', '150000' from the Kimi and Grok and AGY commands that I wrongly added
content = content.replace(', "--autocompact", "150000"', '')

# Now prepend the environment variables to the lists
def add_env(match):
    return match.group(1) + '["/usr/bin/env", "ACCOUNT_AUTOCOMPACT_WINDOW=150000", "BD_MAX_TURNS=20", ' + match.group(2)

content = re.sub(r'(lambda sid, prompt:\s*)\[(.*?)', add_env, content)

with open(file, "w") as f:
    f.write(content)

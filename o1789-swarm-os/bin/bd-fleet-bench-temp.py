file = "/home/mboyle/bin/bd-fleet-bench"
with open(file, "r") as f:
    content = f.read()

content = content.replace('"gemini-3.8-flash"', '"gemini-3.8-flash-high"')
content = content.replace('"gemini-3.1-pro"', '"gemini-3.1-pro-high"')
content = content.replace('"gpt-opus-4.6"', '"claude-opus-4-6-thinking"')
content = content.replace('AGY (GPT Opus 4.6)', 'AGY (Claude Opus 4.6)')
content = content.replace('"gpt-oss"', '"gpt-oss-120b-medium"')

with open(file, "w") as f:
    f.write(content)

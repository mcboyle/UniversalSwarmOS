file = "/home/mboyle/bin/bd-fleet-bench"
with open(file, "r") as f:
    content = f.read()

content = content.replace('"-m", "kimi-code/kimi-for-coding"', '"-m", "kimi-code/kimi-for-coding", "--autocompact", "150000"')
content = content.replace('"--model", "grok-4.7-build-fast"', '"--model", "grok-4.7-build-fast", "--autocompact", "150000"')
content = content.replace('"--conversation", sid', '"--conversation", sid, "--autocompact", "150000"')

with open(file, "w") as f:
    f.write(content)

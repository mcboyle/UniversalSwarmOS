#!/usr/bin/env python3
import sys, json

try:
    payload = json.load(sys.stdin)
    tool_call = payload.get("toolCall", {})
    name = tool_call.get("name")
    args = tool_call.get("args", {})
    
    if name == "view_file":
        path = args.get("AbsolutePath", "")
        # Only block full file reads if they don't specify lines
        if not args.get("StartLine") and not args.get("EndLine"):
            if path.endswith(".py") or path.endswith(".ts") or path.endswith(".js"):
                print(json.dumps({
                    "decision": "deny",
                    "reason": "AST SLICING MANDATE (Rule 58): Full-file reads are prohibited for source code. Use ratf MCP (ctx_slice) to extract specific AST chunks, or specify StartLine/EndLine."
                }))
                sys.exit(0)
                
    # Allow everything else
    print(json.dumps({"decision": "allow"}))
except Exception as e:
    # Fail open
    print(json.dumps({"decision": "allow"}))

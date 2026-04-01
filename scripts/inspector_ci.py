import subprocess
import json
import sys

def run_inspector_command(args):
    """Runs the MCP inspector CLI with the given arguments."""
    command = ["npx", "-y", "@modelcontextprotocol/inspector", "--cli", "uv", "run", "gitingest-mcp"] + args
    print(f"Running: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error executing command: {result.stderr}")
        sys.exit(1)

    # The output might have some NPX install logs or spinner artifacts.
    # We try to extract the JSON block.
    output = result.stdout.strip()

    # Try finding the first '[' or '{' to extract JSON
    start_idx = -1
    for i, char in enumerate(output):
        if char in ('[', '{'):
            start_idx = i
            break

    if start_idx != -1:
        json_str = output[start_idx:]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON output: {e}\nRaw output:\n{output}")
            sys.exit(1)
    else:
        print(f"Could not find JSON in output:\n{output}")
        sys.exit(1)

def validate_tool_schema(tool):
    """Validates the schema of a single tool."""
    name = tool.get('name', 'Unknown')
    print(f"Validating tool: {name}")

    input_schema = tool.get('inputSchema', {})
    schema_str = json.dumps(input_schema)

    errors = []

    # 1. No anyOf allowed
    if 'anyOf' in schema_str:
        errors.append("Schema contains 'anyOf' which is detrimental to LLM steering.")

    # 2. No null allowed
    if '"type": "null"' in schema_str or ': null' in schema_str:
        errors.append("Schema contains 'null' types or defaults.")

    # 3. No "example" or "e.g." in descriptions
    # Descriptions should be pure semantic and not rely on raw string examples.
    # FastMCP handles examples natively via its parameters, so descriptions should be clean.
    description = tool.get('description', '').lower()
    if 'e.g.' in description or 'example' in description:
        errors.append("Tool description contains 'e.g.' or 'example' which should be avoided or placed in proper annotated schema metadata.")

    for prop_name, prop_details in input_schema.get('properties', {}).items():
        prop_desc = prop_details.get('description', '').lower()
        if 'e.g.' in prop_desc or 'example' in prop_desc:
            errors.append(f"Property '{prop_name}' description contains 'e.g.' or 'example'.")

    # Display full schema automatically as requested
    print(json.dumps(tool, indent=2))

    if errors:
        print(f"FAILED validation for tool {name}:")
        for err in errors:
            print(f" - {err}")
        return False

    print(f"Tool {name} is perfectly valid.\n")
    return True

def main():
    print("--- MCP Server CI Inspector Suite ---")

    print("\n1. Listing Tools...")
    response = run_inspector_command(["--method", "tools/list"])

    # Depending on inspector version, the response might be a direct array or wrapped.
    tools = []
    if isinstance(response, dict) and 'tools' in response:
        tools = response['tools']
    elif isinstance(response, list):
        tools = response
    else:
        # Some versions wrap in 'result' -> 'tools'
        tools = response.get('result', {}).get('tools', [])

    if not tools:
        print("No tools found or invalid response format!")
        sys.exit(1)

    all_valid = True
    for tool in tools:
        if not validate_tool_schema(tool):
            all_valid = False

    if not all_valid:
        print("Schema validation failed.")
        sys.exit(1)

    print("\n2. Testing Live Tool Execution...")
    call_response = run_inspector_command([
        "--method", "tools/call",
        "--tool-name", "git_summary",
        "--tool-arg", "owner=puravparab",
        "--tool-arg", "repo=gitingest-mcp",
        "--tool-arg", "branch=main"
    ])

    print("\nTool execution successful! Response:")
    print(json.dumps(call_response, indent=2))

    print("\nCI Suite Completed Successfully.")

if __name__ == "__main__":
    main()
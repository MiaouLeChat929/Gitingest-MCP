# Gitingest-MCP Server How-To Guide

This guide explains how to run the Gitingest MCP Server statelessly, either via standard input/output (STDIO) or HTTP, and how to verify it using the official MCP Inspector.

## 1. Running the Server

The server is built with FastMCP 3.0, meaning it natively supports multiple transports. Because it does not persist any data locally or require any database dependencies, it runs entirely **stateless**. The codebase fetches remote repository structures or downloads zips into memory on-demand.

### Running via STDIO

STDIO is the default and most common way MCP clients communicate with servers. This makes the server run essentially like a CLI tool where clients send JSON-RPC commands through standard input and read standard output.

To run using STDIO:

```bash
# Using the pre-configured entrypoint
uv run gitingest-mcp

# Or by executing the python file directly
uv run python src/gitingest_mcp/server.py
```

*Note: In `server.py`, the code explicitly calls `mcp.run(transport='stdio')`, which enforces the STDIO transport mode.*

### Running via HTTP (Stateless API)

FastMCP supports serving HTTP requests. While STDIO is great for local clients (like Claude Desktop or Cursor), HTTP is often preferred for remote, server-to-server integrations.

To launch the server via HTTP, you can pass arguments to the FastMCP CLI or tweak the python code entrypoint. The simplest way is using the `fastmcp` CLI tool (which comes installed with the dependencies).

```bash
# Run the module with the fastmcp CLI, setting transport to SSE/HTTP
uv run fastmcp run src/gitingest_mcp/server.py:mcp --transport sse --port 8000
```
This boots an HTTP server on `localhost:8000` waiting for standard MCP SSE connections. The server operates completely stateless and tears down the context after each request.

## 2. Using the Official MCP Inspector

The official MCP Inspector is the recommended way to visually test and interact with the server's tools, verifying the JSON schemas, and assuring there are no `anyOf`/`null` schema faults or bad parameters.

To start the Inspector with the `gitingest-mcp` server:

```bash
# Use npx to spin up the inspector and point it to the local uv runner
npx @modelcontextprotocol/inspector uv run gitingest-mcp
```

1. The inspector will launch a web interface, typically on `http://localhost:5173`.
2. Open the URL in your browser.
3. Once loaded, click on the **Tools** tab.
4. You should see three tools registered: `git_summary`, `git_tree`, and `git_files`.
5. **Testing a Tool**:
   - Select `git_summary`.
   - Provide an `owner` (e.g., `puravparab`) and a `repo` (e.g., `gitingest-mcp`).
   - Click "Run".
   - You should receive a summary of the repo, including estimated tokens and a tip to check out the directory tree.
6. **Validating Schemas**:
   - Inspect the input schema for each tool. You will notice clear parameters (owner, repo, branch) without any `anyOf` or `None` types. The instructions will be clear single paragraphs.

## 3. Best Practices Incorporated

If you extend this server, ensure you adhere to the following principles already set in place:
*   **Optimal Tool Constraints**: Avoid `Optional` parameters and fallback to standard empty strings or `"main"` so that LLMs see clean, deterministic JSON schemas without `anyOf` arrays.
*   **Semantic Instructions**: Write tool descriptions as exactly one paragraph.
*   **Semantic Breadcrumbs**: Output strings should end with general hints/breadcrumbs about what the agent might want to do next without dictating explicit tool invocations or naming specific tools.
*   **Stateless execution**: Do not persist states across different tool calls on disk. The class logic handles fetching safely inside the execution context of a single call.
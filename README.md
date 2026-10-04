# Smart Workflows

Document workflows as ordered steps. Each step has Markdown text, **paths**, **CLI commands**, images and a Mermaid diagram. Everything is stored as plain files in `data/` and can be edited through a web UI, a REST API or an MCP server (so an AI model can maintain it).

Python runs in Docker; nothing is installed on the host.

## Run

```bash
docker compose up -d --build web
```

- UI: http://127.0.0.1:8000
- API docs (Swagger): http://127.0.0.1:8000/docs
- Bound to localhost only. Code in `app/` and `static/` is live-mounted with `--reload`.

## Data layout

```
data/workflows/<slug>/workflow.json   # workflow + steps
data/workflows/<slug>/assets/         # uploaded images
```

Step fields: `title`, `description` (MD), `paths[{path,note}]`, `commands[{cmd,shell,cwd,note}]`, `images[{file,caption}]`, `diagram` (Mermaid), `status` (todo | in-progress | done | blocked), `notes` (MD), `tags`.

## REST API (summary)

| Method | Path | |
|---|---|---|
| GET/POST | `/api/workflows` | list / create |
| GET/PATCH/DELETE | `/api/workflows/{slug}` | |
| POST | `/api/workflows/{slug}/steps?position=N` | add step |
| PATCH/DELETE | `/api/workflows/{slug}/steps/{id}` | partial update / delete |
| PUT | `/api/workflows/{slug}/order` | `{"order":[ids]}` |
| POST | `/api/workflows/{slug}/assets` | multipart image upload |
| GET | `/api/search?q=` | search text, paths, commands |

## MCP server (for Claude / other AI clients)

Tools: `list_workflows`, `get_workflow`, `create_workflow`, `update_workflow`, `delete_workflow`, `add_step`, `update_step`, `delete_step`, `reorder_steps`, `add_image`, `remove_image`, `search`.

`add_image` takes either `data_base64` or an http(s) `url` (the container can't read host file paths) and attaches the image to a step.

It runs in a container over stdio and shares the same `data/` folder, so the web UI does not need to be running. Claude Code:

```bash
claude mcp add smart-workflows -- docker compose -f D:/ai-projects/smart-workflows/docker-compose.yml run --rm -T --no-deps mcp
```

Or in a JSON MCP config:

```json
{
  "mcpServers": {
    "smart-workflows": {
      "command": "docker",
      "args": ["compose", "-f", "D:/ai-projects/smart-workflows/docker-compose.yml",
               "run", "--rm", "-T", "--no-deps", "mcp"]
    }
  }
}
```

After changing code in `app/`, rebuild the MCP image (it isn't live-mounted): `docker compose build mcp`.

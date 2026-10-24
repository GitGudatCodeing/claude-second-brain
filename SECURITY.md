# Security

Please report vulnerabilities privately through GitHub: **Security > Report a vulnerability** on this repository. Do not open a public issue.

Scope: `vault-index` (the MCP server on PyPI), the hooks and scripts in this repo. Everything runs locally; the server reads only files under the folders you index and serves them to your MCP client.

Note: the index includes `.json`, `.yaml` and `.toml` files. Keep secrets out of indexed folders, or list their paths in `.indexignore`.

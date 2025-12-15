# Astonish Official Flows Store 🔮

Curated collection of AI automation flows for [Astonish](https://github.com/schardosin/astonish).

## Available Flows

| Flow | Description |
|------|-------------|
| `github_pr_description_generator` | Lists open PRs, lets user pick one, and generates a formatted PR description using LLM analysis |

## Usage

```bash
# List available flows
astonish flows store list

# Install a flow
astonish flows store install github_pr_description_generator

# Run an installed flow
astonish flows run github_pr_description_generator
```

## Contributing

Want to add a flow to the official store? Submit a PR with:
1. Your flow YAML in `flows/`
2. Update `manifest.yaml` with your flow metadata

## License

MIT

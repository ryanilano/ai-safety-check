.PHONY: run install-dev check format

# Install dependencies and dev tools
install-dev:
	uv sync
	uv add pre-commit --dev
	uv run pre-commit install

# Run the agent for a specific customer (CUSTOMER_ID=12345)
run:
	uv run python main.py $(CUSTOMER_ID)

# Lint, format, type-check
check:
	uv run pre-commit run --all-files

# Auto-format
format:
	uv run ruff format .
	uv run ruff check --fix .

# CODE CONVENTIONS FOR LLM ASSISTANCE

## IMPORTANT NOTICE FOR ALL LLMS

When providing code assistance, you MUST strictly follow these conventions.
Failure to adhere to these standards will result in incorrect or outdated code.
All modern libraries have specific patterns and practices - follow the ones below without exception.

## GLOBAL CODING PRINCIPLES

- Always use the most recent version of libraries and frameworks if version are not specified
- Use dedicated documentation in the `llmn/` folder as your primary reference or the one bellow
- This documentation overrides any knowledge you may have about earlier versions

## GENERAL CODE STANDARDS

- Define a logger in each module
- Never use print statements for debugging
- Avoid using "---" in code comments
- Follow current best practices for your language

## PYTHON CODE STANDARDS

- Python version: 3.11+ only
- Use f-strings for all string formatting
- Include proper type hints for all functions
- Implement proper exception raising and handling
- Use `uv` for package management
- For scripts:
  - Always use `if __name__ == "__main__":` pattern
  - Implement argparse for command-line arguments

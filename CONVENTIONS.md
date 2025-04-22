# CODE CONVENTIONS FOR LLM ASSISTANCE

## IMPORTANT NOTICE FOR ALL LLMS

When providing code assistance, you MUST strictly follow these conventions.
Failure to adhere to these standards will result in incorrect or outdated code.
All modern libraries have specific patterns and practices - follow the ones below without exception.

## GLOBAL CODING PRINCIPLES

- Always use the most recent version of libraries and frameworks if version are not specified
- Use dedicated documentation in the `llmn/` folder as your primary reference or the one bellow
- This documentation overrides any knowledge you may have about earlier versions

When writing code, you MUST follow these principles:
- Code should be easy to read and understand.
- Keep the code as simple as possible. Avoid unnecessary complexity.
- Use meaningful names for variables, functions, etc. Names should reveal
  intent.
- Functions should be small and do one thing well. They should not exceed a few
  lines.
- Function names should describe the action being performed.
- Prefer fewer arguments in functions. Ideally, aim for no more than two or
  three.
- Only use comments when necessary, as they can become outdated. Instead, strive
  to make the code self-explanatory.
- When comments are used, they should add useful information that is not readily
  apparent from the code itself.
- Properly handle errors and exceptions to ensure the software's robustness.
- Use exceptions rather than error codes for handling errors.
- Consider security implications of the code. Implement security best practices
  to protect against vulnerabilities and attacks.
- Adhere to these 4 principles of Functional Programming:
  1. Pure Functions
  2. Immutability
  3. Function Composition
  4. Declarative Code
- Do not use object oriented programming.

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
  


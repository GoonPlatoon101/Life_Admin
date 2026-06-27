from agent import Agent
from config import load_config
from llm_service import create_client
from prompts import build_system_prompt


def main() -> None:
    config = load_config()
    system_prompt = build_system_prompt(config)
    agent = Agent(
        config=config,
        client=create_client(config),
        system_prompt=system_prompt,
    )

    response = agent.run()
    if response:
        print(response)


if __name__ == "__main__":
    main()

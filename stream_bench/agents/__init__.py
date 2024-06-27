from .zeroshot import ZeroShotAgent

classes = locals()

TASKS = {
    'zeroshot': ZeroShotAgent
}

def load_agent(agent_name):
    if agent_name in TASKS:
        return TASKS[agent_name]
    if agent_name in classes:
        return classes[agent_name]

    raise ValueError("Agent %s not found" % agent_name)

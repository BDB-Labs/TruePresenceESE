from truepresence.adapter.ese_adapter import evaluate_presence


def run(event):
    return evaluate_presence(event)

import uuid
from redteam.attack_generator import generate_bot_session, generate_llm_user, generate_relay
from redteam.evaluate import run_attack


def run_suite():
    results = []
    s1 = str(uuid.uuid4())
    results.append(run_attack("bot", generate_bot_session(s1)))
    s2 = str(uuid.uuid4())
    results.append(run_attack("llm_user", generate_llm_user(s2)))
    s3 = str(uuid.uuid4())
    results.append(run_attack("relay", generate_relay(s3)))
    return results

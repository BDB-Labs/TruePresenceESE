from truepresence.challenges.engine import Challenge
from truepresence.challenges.response import ChallengeResponse


def score_challenge_response(challenge: Challenge, response: ChallengeResponse) -> dict:
    latency = response.client_latency_ms
    if latency < 250:
        speed_score = 0.9
    elif latency < 800:
        speed_score = 0.5
    else:
        speed_score = 0.2

    coherence_score = 0.6 if len(str(response.response)) > 3 else 0.3

    return {
        "challenge_type": challenge.challenge_type,
        "speed_score": speed_score,
        "coherence_score": coherence_score,
        "relay_indicator": speed_score > 0.7,
    }

from truepresence.challenges.deterministic import stable_challenge_id, stable_index


def test_deterministic_challenge_mapping_is_stable() -> None:
    first_index = stable_index("session-1", 5)
    second_index = stable_index("session-1", 5)
    first_id = stable_challenge_id("session-1", first_index)
    second_id = stable_challenge_id("session-1", second_index)

    assert first_index == second_index
    assert first_id == second_id

from video_captioning_agent.contracts import FrameSample, VideoMetadata
from video_captioning_agent.cvr_client import CVR_SYSTEM_PROMPT, build_cvr_request


def test_cvr_prompt_enforces_factual_boundaries_and_chronology() -> None:
    frames = [
        FrameSample(12, 2.4, "data:image/jpeg;base64,bGF0ZQ=="),
        FrameSample(0, 0.0, "data:image/jpeg;base64,Zmlyc3Q="),
        FrameSample(6, 1.2, "data:image/jpeg;base64,bWlkZGxl"),
    ]
    metadata = VideoMetadata(2.6, 5.0, 13, 32, 24)

    request = build_cvr_request(frames, metadata)
    user_prompt = request["messages"][1]["content"][0]["text"]

    assert "OBSERVABLE FACTS ONLY" in CVR_SYSTEM_PROMPT
    assert "NO SPECULATION" in CVR_SYSTEM_PROMPT
    assert "NO HUMOR OR STYLE" in CVR_SYSTEM_PROMPT
    assert "TEMPORAL AWARENESS" in CVR_SYSTEM_PROMPT
    assert "STRICT JSON" in CVR_SYSTEM_PROMPT

    assert "Prioritize semantically important events" in user_prompt
    assert "clearly visible and relevant" in user_prompt
    assert "If you cannot see something clearly, do not include it" in user_prompt
    assert "presented in chronological order" in user_prompt
    assert "EXACTLY this structure" in user_prompt
    for required_field in (
        '"scene"',
        '"primary_subjects"',
        '"important_objects"',
        '"timeline"',
        '"overall_summary"',
    ):
        assert required_field in user_prompt

    first_timestamp = user_prompt.index("source frame 0): 0.0s")
    middle_timestamp = user_prompt.index("source frame 6): 1.2s")
    last_timestamp = user_prompt.index("source frame 12): 2.4s")
    assert first_timestamp < middle_timestamp < last_timestamp

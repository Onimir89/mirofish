"""Tests for InterviewService."""

from unittest.mock import MagicMock

from app.services.interview_service import InterviewService


def _mock_llm(response='I am a simulated agent.'):
    llm = MagicMock()
    llm.chat.return_value = response
    return llm


def _agent_profile(agent_id='a1', name='Alice'):
    return {
        'agent_id': agent_id,
        'name': name,
        'bio': 'A climate researcher',
        'persona': 'Passionate about science',
        'stance': 'pro-environment',
        'interested_topics': ['climate', 'AI'],
    }


class TestInterviewAgent:
    def test_returns_expected_fields(self):
        llm = _mock_llm()
        svc = InterviewService(llm_client=llm)
        result = svc.interview_agent(_agent_profile(), 'What do you think about AI?')
        assert result['agent_id'] == 'a1'
        assert result['agent_name'] == 'Alice'
        assert result['question'] == 'What do you think about AI?'
        assert result['response'] == 'I am a simulated agent.'
        assert 'timestamp' in result

    def test_builds_prompt_with_profile_info(self):
        llm = _mock_llm()
        svc = InterviewService(llm_client=llm)
        svc.interview_agent(_agent_profile(), 'Hi')
        call_args = llm.chat.call_args
        prompt = call_args[0][0][0]['content']
        assert 'Alice' in prompt
        assert 'climate' in prompt
        assert 'pro-environment' in prompt

    def test_includes_simulation_context(self):
        llm = _mock_llm()
        svc = InterviewService(llm_client=llm)
        ctx = [{'content': 'Posted about climate change', 'action_type': 'post', 'platform': 'twitter'}]
        svc.interview_agent(_agent_profile(), 'Hi', simulation_context=ctx)
        prompt = llm.chat.call_args[0][0][0]['content']
        assert 'Posted about climate change' in prompt


class TestInterviewBatch:
    def test_interviews_multiple_agents(self):
        llm = _mock_llm()
        svc = InterviewService(llm_client=llm)
        profiles = [_agent_profile('a1', 'Alice'), _agent_profile('a2', 'Bob')]
        results = svc.interview_batch(profiles, 'Hello?')
        assert len(results) == 2
        assert results[0]['agent_id'] == 'a1'
        assert results[1]['agent_id'] == 'a2'
        assert llm.chat.call_count == 2

    def test_passes_per_agent_context(self):
        llm = _mock_llm()
        svc = InterviewService(llm_client=llm)
        profiles = [_agent_profile('a1', 'Alice')]
        ctx = {'a1': [{'content': 'tweet content', 'action_type': 'post', 'platform': 'twitter'}]}
        svc.interview_batch(profiles, 'Hi', simulation_context=ctx)
        prompt = llm.chat.call_args[0][0][0]['content']
        assert 'tweet content' in prompt


class TestGetHistory:
    def test_empty_history(self):
        svc = InterviewService(llm_client=_mock_llm())
        assert svc.get_history('sim1') == []

    def test_records_and_retrieves(self):
        svc = InterviewService(llm_client=_mock_llm())
        interviews = [{'agent_id': 'a1', 'response': 'hi'}]
        svc.record_interviews('sim1', interviews)
        history = svc.get_history('sim1')
        assert len(history) == 1
        assert history[0]['agent_id'] == 'a1'

    def test_appends_to_existing_history(self):
        svc = InterviewService(llm_client=_mock_llm())
        svc.record_interviews('sim1', [{'agent_id': 'a1'}])
        svc.record_interviews('sim1', [{'agent_id': 'a2'}])
        assert len(svc.get_history('sim1')) == 2

    def test_separate_simulation_histories(self):
        svc = InterviewService(llm_client=_mock_llm())
        svc.record_interviews('sim1', [{'agent_id': 'a1'}])
        svc.record_interviews('sim2', [{'agent_id': 'a2'}])
        assert len(svc.get_history('sim1')) == 1
        assert len(svc.get_history('sim2')) == 1

"""Agent interview service - ask questions to simulated agents."""

from datetime import datetime

from app.utils.llm_client import LLMClient


class InterviewService:
    """Interview simulated agents in-character."""

    def __init__(self, llm_client: LLMClient = None):
        self.llm = llm_client or LLMClient()
        self.history: dict[str, list[dict]] = {}  # simulation_id -> interviews

    def interview_agent(
        self,
        agent_profile: dict,
        question: str,
        simulation_context: list[dict] | None = None,
    ) -> dict:
        """Interview a single agent. Returns the agent's in-character response.

        Args:
            agent_profile: Agent profile dict with name, bio, persona, stance, topics.
            question: The interviewer's question.
            simulation_context: Recent posts/actions by this agent (optional).

        Returns:
            Dict with agent_id, agent_name, question, response, timestamp.
        """
        agent_name = agent_profile.get('name', 'Unknown')
        agent_bio = agent_profile.get('bio', '')
        agent_persona = agent_profile.get('persona', '')
        stance = agent_profile.get('stance', 'neutral')
        topics = ', '.join(agent_profile.get('interested_topics', []))
        agent_id = agent_profile.get('agent_id', '')

        # Build context from recent activity
        context_block = ''
        if simulation_context:
            lines = []
            for item in simulation_context[:10]:
                content = item.get('content', '')
                action_type = item.get('action_type', 'post')
                platform = item.get('platform', '')
                lines.append(f"- [{action_type} on {platform}]: {content[:200]}")
            context_block = (
                "\n\nYour recent activity on social media:\n"
                + "\n".join(lines)
            )

        prompt = (
            f"You are {agent_name}, {agent_bio}.\n"
            f"Personality: {agent_persona}\n"
            f"Your stance: {stance}\n"
            f"Topics you care about: {topics}\n"
            f"{context_block}\n\n"
            f"An interviewer asks you the following question. "
            f"Respond naturally and in-character, as yourself. "
            f"Keep your answer concise (2-4 sentences) unless the question "
            f"requires more detail.\n\n"
            f"Question: {question}"
        )

        response_text = self.llm.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.8,
        )

        return {
            'agent_id': agent_id,
            'agent_name': agent_name,
            'question': question,
            'response': response_text,
            'timestamp': datetime.now().isoformat(),
        }

    def interview_batch(
        self,
        agent_profiles: list[dict],
        question: str,
        simulation_context: dict[str, list[dict]] | None = None,
    ) -> list[dict]:
        """Interview multiple agents with the same question.

        Args:
            agent_profiles: List of agent profile dicts.
            question: The interviewer's question.
            simulation_context: Dict mapping agent_id -> recent posts (optional).

        Returns:
            List of interview result dicts.
        """
        results = []
        context_map = simulation_context or {}
        for profile in agent_profiles:
            agent_id = profile.get('agent_id', '')
            ctx = context_map.get(agent_id)
            result = self.interview_agent(profile, question, ctx)
            results.append(result)
        return results

    def interview_all(
        self,
        all_profiles: list[dict],
        question: str,
        simulation_context: dict[str, list[dict]] | None = None,
    ) -> list[dict]:
        """Interview every agent.

        Args:
            all_profiles: All agent profiles in the simulation.
            question: The interviewer's question.
            simulation_context: Dict mapping agent_id -> recent posts (optional).

        Returns:
            List of interview result dicts.
        """
        return self.interview_batch(all_profiles, question, simulation_context)

    def record_interviews(
        self, simulation_id: str, interviews: list[dict],
    ):
        """Record interviews in history."""
        if simulation_id not in self.history:
            self.history[simulation_id] = []
        self.history[simulation_id].extend(interviews)

    def get_history(self, simulation_id: str) -> list[dict]:
        """Get interview history for a simulation."""
        return self.history.get(simulation_id, [])

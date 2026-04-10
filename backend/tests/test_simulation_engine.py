"""Tests for SimulationEngine helper methods."""

from app.services.simulation_engine import SimulationEngine, SimulationState, Post


def _make_engine():
    """Create an engine with minimal config and two agents."""
    profiles = [
        {'agent_id': 'a1', 'name': 'Alice', 'interested_topics': ['AI', 'climate']},
        {'agent_id': 'a2', 'name': 'Bob', 'interested_topics': ['sports']},
    ]
    config = {
        'time': {'minutes_per_round': 60, 'total_simulation_hours': 1},
        'agents': [
            {'agent_id': 'a1', 'activity_level': 'high', 'posts_per_hour': 1},
            {'agent_id': 'a2', 'activity_level': 'low', 'posts_per_hour': 0.5},
        ],
        'platform': {
            'recency_weight': 0.4,
            'popularity_weight': 0.3,
            'relevance_weight': 0.3,
        },
        'events': {},
    }
    return SimulationEngine(
        simulation_id='test-sim',
        profiles=profiles,
        config=config,
        llm_client=None,
    )


class TestGetPlatformPosts:
    def test_twitter_returns_twitter_list(self):
        engine = _make_engine()
        assert engine._get_platform_posts('twitter') is engine.state.twitter_posts

    def test_reddit_returns_reddit_list(self):
        engine = _make_engine()
        assert engine._get_platform_posts('reddit') is engine.state.reddit_posts

    def test_unknown_platform_returns_reddit(self):
        engine = _make_engine()
        # Non-twitter defaults to reddit_posts
        assert engine._get_platform_posts('mastodon') is engine.state.reddit_posts


class TestFindPost:
    def test_finds_existing_post(self):
        engine = _make_engine()
        post = Post(
            id='p1', agent_id='a1', agent_name='Alice',
            content='Hello world', platform='twitter',
            timestamp='2025-01-01T00:00:00', round_num=1,
        )
        engine._add_post(post)
        found = engine._find_post('p1', 'twitter')
        assert found is not None
        assert found['id'] == 'p1'

    def test_returns_none_for_missing(self):
        engine = _make_engine()
        assert engine._find_post('nonexistent', 'twitter') is None

    def test_wrong_platform_returns_none(self):
        engine = _make_engine()
        post = Post(
            id='p2', agent_id='a1', agent_name='Alice',
            content='Reddit post', platform='reddit',
            timestamp='2025-01-01T00:00:00', round_num=1,
        )
        engine._add_post(post)
        assert engine._find_post('p2', 'twitter') is None
        assert engine._find_post('p2', 'reddit') is not None


class TestScorePost:
    def test_returns_float(self):
        engine = _make_engine()
        post_dict = {
            'id': 'p1', 'content': 'AI is great', 'likes': 5,
            'reposts': 2, 'upvotes': 0, 'comments': [],
        }
        score = engine._score_post(post_dict, ['AI', 'climate'], total_posts=10, post_index=5)
        assert isinstance(score, float)

    def test_higher_relevance_increases_score(self):
        engine = _make_engine()
        post_relevant = {
            'id': 'p1', 'content': 'AI and climate change discussion',
            'likes': 0, 'reposts': 0, 'upvotes': 0, 'comments': [],
        }
        post_irrelevant = {
            'id': 'p2', 'content': 'Nothing related here',
            'likes': 0, 'reposts': 0, 'upvotes': 0, 'comments': [],
        }
        topics = ['AI', 'climate']
        score_r = engine._score_post(post_relevant, topics, total_posts=10, post_index=5)
        score_i = engine._score_post(post_irrelevant, topics, total_posts=10, post_index=5)
        assert score_r > score_i

    def test_higher_popularity_increases_score(self):
        engine = _make_engine()
        post_popular = {
            'id': 'p1', 'content': 'test', 'likes': 20,
            'reposts': 10, 'upvotes': 0, 'comments': ['c1', 'c2'],
        }
        post_unpopular = {
            'id': 'p2', 'content': 'test', 'likes': 0,
            'reposts': 0, 'upvotes': 0, 'comments': [],
        }
        score_p = engine._score_post(post_popular, [], total_posts=10, post_index=5)
        score_u = engine._score_post(post_unpopular, [], total_posts=10, post_index=5)
        assert score_p > score_u

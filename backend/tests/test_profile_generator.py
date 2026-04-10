"""Tests for ProfileGenerator defaults and format conversion."""

from app.services.profile_generator import ProfileGenerator, _PROFILE_DEFAULTS


def _sample_profile():
    """A fully populated profile dict for testing."""
    return {
        'name': 'Alice Chen',
        'username': 'alicechen42',
        'bio': 'Climate researcher & AI enthusiast',
        'persona': 'Passionate, detail-oriented, posts threads',
        'age': 32,
        'gender': 'female',
        'mbti': 'INTJ',
        'profession': 'Research Scientist',
        'karma': 5000,
        'follower_count': 12000,
        'friend_count': 300,
        'country': 'Canada',
        'interested_topics': ['climate', 'AI', 'policy'],
        'stance': 'pro-science',
        'activity_level': 'high',
        'posting_frequency': 'daily',
        'tone': 'earnest',
        'preferred_topics': ['climate policy', 'ML research'],
        'agent_id': 'abc123',
        'created_at': '2025-01-01T00:00:00',
    }


class TestProfileDefaults:
    def test_all_default_keys_present(self):
        """Every key in _PROFILE_DEFAULTS should exist."""
        for key in _PROFILE_DEFAULTS:
            assert key in _PROFILE_DEFAULTS

    def test_default_age_is_int(self):
        assert isinstance(_PROFILE_DEFAULTS['age'], int)

    def test_default_lists_are_lists(self):
        assert isinstance(_PROFILE_DEFAULTS['interested_topics'], list)
        assert isinstance(_PROFILE_DEFAULTS['preferred_topics'], list)


class TestToTwitterFormat:
    def test_maps_fields_correctly(self):
        profile = _sample_profile()
        tw = ProfileGenerator.to_twitter_format(profile)
        assert tw['name'] == 'Alice Chen'
        assert tw['screen_name'] == 'alicechen42'
        assert tw['description'] == profile['bio']
        assert tw['location'] == 'Canada'
        assert tw['followers_count'] == 12000
        assert tw['friends_count'] == 300
        assert tw['agent_id'] == 'abc123'

    def test_verified_true_above_10k_followers(self):
        profile = _sample_profile()
        profile['follower_count'] = 15000
        tw = ProfileGenerator.to_twitter_format(profile)
        assert tw['verified'] is True

    def test_verified_false_below_10k_followers(self):
        profile = _sample_profile()
        profile['follower_count'] = 500
        tw = ProfileGenerator.to_twitter_format(profile)
        assert tw['verified'] is False

    def test_handles_missing_fields(self):
        tw = ProfileGenerator.to_twitter_format({})
        assert tw['name'] == ''
        assert tw['followers_count'] == 0
        assert tw['verified'] is False

    def test_interested_topics_carried_over(self):
        profile = _sample_profile()
        tw = ProfileGenerator.to_twitter_format(profile)
        assert tw['interested_topics'] == ['climate', 'AI', 'policy']


class TestToRedditFormat:
    def test_maps_fields_correctly(self):
        profile = _sample_profile()
        rd = ProfileGenerator.to_reddit_format(profile)
        assert rd['username'] == 'alicechen42'
        assert rd['display_name'] == 'Alice Chen'
        assert rd['karma'] == 5000
        assert rd['subscribed_subreddits'] == ['climate', 'AI', 'policy']
        assert rd['agent_id'] == 'abc123'

    def test_karma_split_60_40(self):
        profile = _sample_profile()
        profile['karma'] = 1000
        rd = ProfileGenerator.to_reddit_format(profile)
        assert rd['comment_karma'] == 600
        assert rd['post_karma'] == 400

    def test_cake_day_from_created_at(self):
        profile = _sample_profile()
        rd = ProfileGenerator.to_reddit_format(profile)
        assert rd['cake_day'] == profile['created_at']

    def test_preferred_topics_carried_over(self):
        profile = _sample_profile()
        rd = ProfileGenerator.to_reddit_format(profile)
        assert rd['preferred_topics'] == ['climate policy', 'ML research']

    def test_handles_missing_fields(self):
        rd = ProfileGenerator.to_reddit_format({})
        assert rd['username'] == ''
        assert rd['karma'] == 0
        assert rd['comment_karma'] == 0

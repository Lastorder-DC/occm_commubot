import os
from mastodon import Mastodon
import pytest
from unittest.mock import Mock
from dotenv import load_dotenv

load_dotenv(".env.test")

# Define test cases for on_notification function
def test_on_notification_no_keyword(mocker):
    # Create a mock Mastodon instance
    mastodon_mock = Mock(spec=Mastodon)
    mocker.patch('masto_search_bot.Mastodon', return_value=mastodon_mock)

    from splatoon_schedule_bot import Listener

    # Test with a mention that does not contain [ ] keywords
    notification = {
        'type': 'mention',
        'status': {
            'account': {'acct': 'user'},
            'content': '<p>키워드 없는 멘션 테스트</p>',
            'id': '110801602568153607'
        }
    }
    
    # Create a mock Mastodon instance
    mastodon_mock = Mock(spec=Mastodon)
    mocker.patch('masto_search_bot.Mastodon', return_value=mastodon_mock)
    
    # Instantiate the Listener class
    listener = Listener()
    
    # Call the on_notification method
    listener.on_notification(notification)
    
    # Assert that the Mastodon API was not called
    mastodon_mock.status_post.assert_not_called()

def test_on_notification_with_keyword(mocker):
    # Create a mock Mastodon instance
    mastodon_mock = Mock(spec=Mastodon)
    mocker.patch('masto_search_bot.Mastodon', return_value=mastodon_mock)

    from splatoon_schedule_bot import Listener

    # Test with a mention that contains [ ] keyword
    notification = {
        'type': 'mention',
        'status': {
            'account': {'acct': 'user'},
            'content': '<p>[도서관] 도서관을 본다</p>',
            'id': '110801602568153607'
        }
    }
    
    # Instantiate the Listener class
    listener = Listener()
    
    # Call the on_notification method
    listener.on_notification(notification)
    
    # Assert that the Mastodon API was called with the correct reply
    mastodon_mock.status_post.assert_called_once_with(
        '@user 이곳은 조용하다. 사서가 이쪽을 힐끔 쳐다보다가 시선을 돌린다.',
        in_reply_to_id='110801602568153607',
        visibility='public'
    )

# Add more test cases as needed to cover different scenarios

if __name__ == '__main__':
    pytest.main()

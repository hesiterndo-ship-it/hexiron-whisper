from services.moderation import looks_spam
def test_spam(): assert looks_spam('crypto giveaway')
def test_clean(): assert not looks_spam('سلام')

import os, twitter, re, json, requests, time, pytz
from datetime import datetime

# NLP tools
import nltk
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import TweetTokenizer
from nltk.corpus import wordnet
lemma = WordNetLemmatizer()

# NB: splits off #s and @s; otherwise, use TweetTokenizer().tokenize 
tokenizer = nltk.word_tokenize 

spacexdir = os.path.expanduser('~/github/spacex_smartweets/')
keys = os.path.join(spacexdir, 'keys.json')
seentweets = os.path.join(spacexdir, 'seen_tweets.txt')
log = os.path.join(spacexdir,'log.txt')

# get authorization keys
with open(keys, 'r') as infile:
    keys = json.load(infile)
    
# get last collected tweets
with open(seentweets, 'r') as infile:
    seen_tweets = infile.read().split()
    
with open(log, 'r') as infile:
    log_file = infile.read()

# instance Twitter-API
api = twitter.Api(**keys['twitter'], tweet_mode='extended')

def closeSession(log_file, seen_tweets):
    """Write final files."""
    with open(log, 'w') as outfile:
        outfile.write(log_file)
    with open(seentweets, 'w') as outfile:
        outfile.write(seen_tweets)

def get_wordnet_pos(word):
    """ Map POS tag to first character lemmatize() accepts.

    Credit: https://www.machinelearningplus.com/nlp/lemmatization-examples-python/
    ^ which saved me some time from thinking through this...
    """
    tag = nltk.pos_tag([word])[0][1][0].upper()
    tag_dict = {
        'J': wordnet.ADJ,
        'N': wordnet.NOUN,
        'V': wordnet.VERB,
        'R': wordnet.ADV
    }
    return tag_dict.get(tag, wordnet.NOUN)

def lemmatizeTweet(tweetstring):
    """Lemmatize and lowercase tweet text.

    Returns a set of lemmas.
    """
    lower_words = [w.lower() for w in tokenizer(tweetstring)]
    pos_words = [get_wordnet_pos(w) for w in lower_words]
    lemmas = [
        lemma.lemmatize(w, pos) 
            for w, pos in zip(lower_words, pos_words)
    ]
    return lemmas

def matchWords(lemmas, regex):
    """Iterate through lemmas and look for match."""
    regex = re.compile(regex)
    for lemma in lemmas:
        match = regex.match(lemma)
        if match: 
            return match
    return match 

def matchTweet(tweet, match_terms):
    """Match tweets using regex.

    Args:
        tweet: twitter Status object
        match_terms: a set of terms to be 
            joined on | for regex matching
    Returns:
        boolean on whether a match
    """
    if tweet is None:
        return None 
    tweet_lemmas = lemmatizeTweet(tweet.full_text)
    match_pattern = '|'.join(match_terms)
    re_match = matchWords(tweet_lemmas, match_pattern)
    return re_match 

def formatTweetURL(user, status_id):
    """Returns formatted URL for tweets."""
    return f'https://twitter.com/{user}/status/{status_id}'

# Tweet Triggers, Organized by "domain"
# Terms support regex pattern matching
# NB: all tweet strings are lowercased for matching
starship = {
    'starship', 'sn\d+', 'bn\d+', 
    'superheavy', 'raptor', 'bellyflop'
    'hopper', 'tps'
} 

bocachica = {
    'bay', 'highbay', 'midbay',
    'boca', 'chica', 'starbase', 
    'shipyard'
}

starbase = starship | bocachica

spacecraft = {
    'thrust', 'rocket', 'isp', 
    'pad', 'engine', 'fairing', 'booster', 
    'propellant', 'ch4', 'turbopump', 'nosecone',
    'tank', 'flap',
}
spacexthings = {
    'falcon', 'merlin', 'ocisly', 'octagrabber', 
    'octograbber', 'jrti', 'droneship', 'starlink', 
    '39a', 'dragon', 'draco', 'superdraco',
}

missions = {'dearmoon'}

spacexthings |= missions

space = {
    'space', 'mars', 'orbit', 'orbital', 'flight', 
    'crewed', 'launch', 'moon', 'lunar'
}

testing = {
    'test','road', 'close', 'open', 'shut',
    'reopen', 'sheriff', 'vent', 'loud', 
    'sound', 'site', 'launch', 'hover', 'hop',
    'roar', 'rumble', 'lit', 'flash', 'flare',
    'explosion', 'explode', 'visible', 'shut',
    'block', 'roadblock', 'notam', 'tfr', 'tfrs',
    'hangar', 'foundation'
}

mcgregor = {'mcgregor', 'raptor', 'test', 'loud', '#spacextests', 'roar'}

spacex_mentions = {'spacex'} 
elon_mentions = {'elonmusk'}
nasa_mentions = {'nasa'} 

# People/tweets to track + their triggers
people = {
    '@elonmusk': {
        'real_name':'Elon Musk',
        'triggers': starbase|spacexthings|spacecraft|space|spacex_mentions|nasa_mentions,
        'replies': True,
        'bio': 'the one and only'
     },
    '@bocachicagal': {
        'real_name':'Mary',
        'triggers': testing|starbase,
        'bio': 'posts updates on tests'
     },
    '@RGVReagan': {
        'real_name': 'Mark Reagan',
        'triggers': spacex_mentions|starbase|elon_mentions,
        'replies': True,
        'bio': 'journalist with @Brownsvillenews'
    },
    '@SpacePadreIsle': {
        'real_name': 'Spadre',
        'triggers': spacex_mentions|starbase|testing,
        'bio': 'spadre surfing'
    },
    '@SpaceX': {
        'real_name': 'Space Exploration Technologies',
        'triggers': set(),
        'all_tweets': True,
        'replies': True,
        'bio': 'the big one'
    },
    '@austinbarnard45': {
        'real_name': 'Austin Barnard',
        'triggers': testing|starbase,
        'bio': 'Local who takes pictures and streams sometimes'
    },
    '@bluemoondance74': {
        'real_name': 'Reagan Beck',
        'triggers': {'spacextests','#spacextests'}, 
        'bio': 'Lives near McGregor test facility'
    },
    '@Teslarati': {
        'real_name': 'Teslarati',
        'triggers': spacexthings|starbase|nasa_mentions|spacex_mentions,
        'replies': True,
        'bio': 'News'
    },
    '@Erdayastronaut': {
        'real_name': 'Tim Dodd',
        'triggers': spacexthings|starbase,
        'bio': 'Space Youtuber'
    },
    '@SciGuySpace': {
        'real_name': 'Eric Berger',
        'triggers': spacexthings|spacex_mentions|elon_mentions|starbase,
        'bio': 'Senior Space Editor at Ars Technica'
    },
    '@_brendan_lewis': {
        'real_name': 'Brendan',
        'triggers': starbase,
        'media': True,
        'bio': 'Tweets diagrams'
    },
#    '@TrevorMahlmann': {
#        'real_name': '',
#        'triggers': spacex_mentions|starbase|spacexthings,
#        'media': True,
#        'bio': 'Tweets photos'
#    },
    '@ErcXspace': {
        'real_name': '',
        'triggers': starbase,
        'media': True,
        'bio': 'Tweets renders'
    },
    '@Neopork85': {
        'real_name': '',
        'triggers': starbase,
        'media': True,
        'bio': 'Tweets renders'
    },
    '@C_Bass3d': {
        'real_name': 'Corey',
        'triggers': starship,
        'media': True,
        'bio': '3D models'
    },
    '@RGVaerialphotos': {
        'real_name': '',
        'triggers': spacex_mentions|starbase|spacexthings,
        'media': True,
        'bio': 'Tweets aerials'
    },
    '@EmreKelly': {
        'real_name': 'Emre Kelly',
        'triggers': spacex_mentions|spacexthings|starbase|elon_mentions,
        'bio': 'Space reporter @Florida_today & @usatoday'
    },
    '@fael097': {
        'real_name': 'Rafael Adamy',
        'triggers': starbase,
        'bio': 'builds SNX diagrams'
    },
    '@NASASpaceflight': {
        'real_name': 'Chris B',
        'triggers': starbase,
        'bio': 'Runs Nasaspaceflight'
    },
    '@nextspaceflight': {
        'real_name': 'Michael Baylor',
        'triggers': starbase,
        'bio': 'Works for Nasaspaceflight'
    },
    '@TheFavoritist': {
        'real_name': 'Brady Kenniston',
        'triggers': starbase,
        'bio': 'Works for Nasaspaceflight'
    },
    '@thejackbeyer': {
        'real_name': 'Jack Beyer',
        'triggers': starbase,
        'bio': 'Works for Nasaspaceflight'
    },
    '@BocaRoad': {
        'real_name': '',
        'triggers': {'closure'},
        'all_tweets': True,
        'bio': 'Posts road closures'
    },

}

def searchTweets(log_file=log_file, seen_tweets=seen_tweets):
        
    # check network connection
    try:
        requests.get('http://x.com') # Elon's tiny website :)
    except requests.ConnectionError:
        log_file += f'{datetime.now().__str__()}\t\tno connection\n'
        closeSession(log_file, ' '.join(seen_tweets))
        return None

    for person, userdat in people.items():

        # load all eligible tweets
        do_replies = userdat.get('replies', False)
        user_tweets = api.GetUserTimeline(
            screen_name=person, 
            include_rts=userdat.get('retweets', False), 
            exclude_replies=(not do_replies),
            count=20
        )

        # scan tweets for matches
        for tweet in user_tweets:

            # skip seen tweets or those older than 30 mins (1800 secs)
            now = datetime.now(tz=pytz.utc) 
            tweet_time = datetime.strptime(tweet.created_at, '%a %b %d %H:%M:%S +0000 %Y')\
                .replace(tzinfo=pytz.utc)	
            tweet_age = (now - tweet_time).total_seconds()
            if tweet.id_str in seen_tweets or tweet_age > 4000:
                continue

            # if tweet is a reply:
            # check whether the reply is in response to a matching tweet
            if do_replies:
                try:
                    original_tweet = api.GetStatus(tweet.in_reply_to_status_id) if tweet.in_reply_to_status_id else None
                except: # if orig. tweet is missing
                    original_tweet = None
            else:
                original_tweet = None

            # search for tweet matches
            match_terms = userdat['triggers']
            tweet_match = matchTweet(tweet, match_terms) 
            orig_match = matchTweet(original_tweet, match_terms)
            match_media = (
                userdat.get('media', False)
                and bool(getattr(tweet, 'media', False))
            )
            match_alltweets = userdat.get('all_tweets', False)
            is_match = any([
                bool(tweet_match),
                bool(orig_match),
                match_alltweets,
                match_media,
            ])

            # trigger a notification if match
            if is_match:
                
                # format and ship tweet and data
                tweet_url = formatTweetURL(person, tweet.id_str)

                # rm twitter URLs; prevents Slack from double-preview
                clean_text = re.split(
                    'https://t.co', 
                    tweet.full_text, 
                    maxsplit=1
                )
                clean_text = clean_text[0].strip() 

                # format pushed message
                match = tweet_match or orig_match or ['']
                if not match[0] and match_media:
                    match = ['MEDIA']
                person_name = tweet.user.name
                
                send_text = f'`• {person_name} •`\n{clean_text}\n{tweet_url} "_{match[0]}_"'

                # add original tweet if the tweet is a reply to an unseen other tweet
                if orig_match and (original_tweet.id_str not in seen_tweets):
                    orig_name = original_tweet.user.name
                    orig_text = original_tweet.full_text
                    send_text = (
                        f'`• {orig_name} •`\n{orig_text}\n'
                        '|\n'
                        '|\n'
                        '|\n'
                    ) + send_text

                # push Slack post
                requests.post(
                    url=keys['slack']['webhook'], 
                    data=json.dumps({'text':send_text})
                ) 
                # push Discord post
                #requests.post(url=keys['discord']['webhook'],
                #              data=json.dumps({'content':send_text}))

                # log match data 
                tweet_match = tweet_match or ['']
                orig_match = orig_match or ['']
                seen_tweets.append(tweet.id_str)
                log_file += (
                    f'{datetime.now().__str__()}\t\ttrigger {tweet.id_str} ({person} ) '
                    f'| tweet matches: {tweet_match[0]} '
                    f'| reply matches: {orig_match[0]} '
                    f'| media match: {match_media} '
                    f'| tweet_age: {tweet_age}\n'
                )
    
    # add final report to log file
    log_file += f'{datetime.now().__str__()}\t\tcompleted search\n'
    closeSession(log_file, ' '.join(seen_tweets))

# call the search
searchTweets()

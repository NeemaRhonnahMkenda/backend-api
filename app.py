import os
import urllib
from logging.config import dictConfig

import certifi
import mongoengine
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
from dateutil import parser

DB_COLLECTIONS = [
    'players',
    'teams',
    'competitions',
    'matches',
    'fixtures',
    'bodies'
]

# flask logging setup, may not end up being used
dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})

# main application setup
app = Flask(__name__)
app.config['MONGODB_SETTINGS'] = {'DB': 'ea_eye'}
cors = CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000/"}})
CORS(app)

# MongoDB setup and initialization
db_username = urllib.parse.quote_plus(os.environ['DB_USERNAME'])
db_password = urllib.parse.quote_plus(os.environ['DB_PASSWORD'])
db_uri = os.environ['DB_URI'].format(db_username, db_password)
db = mongoengine.connect(alias='default', host=db_uri, tlsCAFile=certifi.where())
db = db.ea_eye


@app.route('/api/v3/players_mike', methods=['GET'])
def get_all_players():
    # Assuming 'players' is the collection containing player details

    projection = {'name': 1, 'dob': 1, 'jersey_num': 1, 'stats.min_played': 1, 'nationality': 1, 'position': 1,
                  'stats.goals': 1, 'stats.clean_sheets': 1, 'stats.assists': 1, 'stats.match_day_squad': 1,
                  'performance.mins': 1, 'performance.appearances': 1, 'performance.assists': 1,
                  'performance.team_matches': 1, 'performance.clean_sheets': 1, 'performance.percent_matches': 1,
                  'performance.percent_potential_mins': 1, 'performance.goals_per_90': 1,
                  }
    players = db.players.find({}, projection)

    # Convert ObjectId to string for JSON serialization
    players_list = []
    for player in players:
        # Calculate age based on the 'dob' field
        age = calculate_age(player.get('dob'))

        # Check if the player has 'performance' data
        if 'performance' in player:
            performance_data = player['performance']
        else:
            # If 'performance' is not present, set all attributes to 0
            performance_data = {'mins': 0, 'appearances': 0, 'assists': 0,
                                'team_matches': 0, 'clean_sheets': 0,
                                'percent_matches': 0, 'percent_potential_mins': 0, 'goals_per_90': 0, }

        # Check if the player has a position, if not, set it to "Not Available"
        position = player.get('position', 'Not Available')

        goals = player['stats'].get('goals', [])
        # Check if goals is iterable (list or another iterable)
        if isinstance(goals, (list, tuple, set)):
            total_goals = sum(goal['minute'] is not None for goal in goals)
        else:
            total_goals = 0  # or handle it according to your logic

        # Append the age and 'performance' data to the player's data
        player_data = {
            '_id': str(player['_id']),
            'name': player.get('name', ''),
            'nationality': player.get('nationality', ''),
            'position': position,
            'dob': player.get('dob', ''),
            'jersey_num': player.get('jersey_num', ''),
            'minutes_played': player['stats'].get('min_played', 0),
            'total_goals': total_goals,
            'clean_sheets': player['stats'].get('clean_sheets', 0),
            'assists': player['stats'].get('assists', 0),
            'match_day_squad': player['stats'].get('match_day_squad', 0),
            'age': age,
            'mins': performance_data.get('mins', 0),
            'appearances': performance_data.get('appearances', 0),
            'Assists': performance_data.get('assists', 0),
            'team_matches': performance_data.get('team_matches', 0),
            'Clean_sheets': performance_data.get('clean_sheets', 0),
            'percent_matches': performance_data.get('percent_matches', 0),
            'percent_potential_mins': performance_data.get('percent_potential_mins', 0),
            'goals_per_90': performance_data.get('goals_per_90', 0),
        }

        players_list.append(player_data)
    return jsonify(players_list)


@app.route('/api/v3/competition_players', methods=['POST'])
def get_competition_players():
    try:
        # Extract the user's name from the request
        username = request.json.get('username')

        if not username:
            return jsonify({'error': 'User name is missing in the request'}), 400

        # Assuming 'competitions' is the collection containing competition details
        # Find the competition assigned to the user
        competition = db.competitions.find_one({'assigned_users': username})

        if competition:
            competition_name = competition.get('name')

            # Find players associated with the competition
            players_in_competition = db.players.find({'competition': competition_name})

            # Prepare the response data
            competition_players = []
            for player in players_in_competition:
                player_data = {
                    'name': player.get('name'),
                    'position': player.get('position'),
                    'nationality': player.get('nationality'),
                    # Add other relevant player data as needed
                }
                competition_players.append(player_data)

            return jsonify({'competition': competition_name, 'players': competition_players})
        else:
            return jsonify({'error': 'No competition assigned to the user'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v3/radar_chart', methods=['POST'])
def get_radar_chart_data():
    try:
        selected_players = request.json.get('selectedPlayers', [])
        if not selected_players:
            return jsonify({'error': 'No players selected'}), 400

        # Assuming 'players' is the collection containing player details
        projection = {'name': 1, 'stats.min_played': 1, 'stats.goals': 1, 'stats.clean_sheets': 1,
                      'stats.assists': 1, 'stats.match_day_squad': 1}

        players_data = []

        for player_name in selected_players:
            player = db.players.find_one({'name': player_name}, projection)

            if player:
                goals = player['stats'].get('goals', [])
                total_goals = sum(goal['minute'] is not None for goal in goals) if isinstance(goals,
                                                                                              (list, tuple, set)) else 0

                player_data = {
                    'name': player.get('name', ''),
                    'minutes_played': player['stats'].get('min_played', 0),
                    'total_goals': total_goals,
                    'clean_sheets': player['stats'].get('clean_sheets', 0),
                    'assists': player['stats'].get('assists', 0),
                    'match_day_squad': player['stats'].get('match_day_squad', 0),
                }

                players_data.append(player_data)
            else:
                return jsonify({'error': f'Player {player_name} not found'}), 404

        radar_chart_data = {
            'params': ['minutes_played', 'total_goals', 'clean_sheets', 'assists', 'match_day_squad'],
            'ranges': [(0, 200), (0, 20), (0, 10), (0, 15), (0, 25)],  # Update with your desired ranges
            'values': [list(player_data.values())[1:] for player_data in players_data],
            'title': {
                'title_name': f'{players_data[0]["name"]} vs {players_data[1]["name"]}',
                'title_color': 'red',
                'subtitle_name': 'Subtitle 1',
                'subtitle_color': 'red',
                'title_name_2': 'Subtitle 2',
                'title_color_2': 'red',
                'subtitle_name_2': 'Subtitle 2',
                'subtitle_color_2': 'red',
                'title_fontsize': 18,
                'subtitle_fontsize': 15,
            },
            'endnote': '@michaelkhanda\ndata via FBREF / EA Eye',
        }

        return jsonify(radar_chart_data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v3/nationalities', methods=['GET'])
def get_unique_nationalities():
    # Assuming 'players' is the collection containing player details
    projection = {'nationality': 1}
    players = db.players.find({}, projection)

    # Use a set to store unique nationalities
    unique_nationalities1 = set()
    unique_nationalities = set()

    for player in players:
        nationality = player.get('nationality')
        if nationality:
            unique_nationalities1.add(nationality)
            unique_nationalities = sorted(unique_nationalities1)

    # Convert the set to a list before returning JSON
    nationalities_list = list(unique_nationalities)

    return jsonify(nationalities_list)


@app.route('/api/v3/positions', methods=['GET'])
def get_unique_positions():
    projection = {'position': 1}
    players = db.players.find({}, projection)

    # Use a set to store unique nationalities
    unique_position = set()

    for player in players:
        position = player.get('position')
        if position:
            unique_position.add(position)

    # Convert the set to a list before returning JSON
    position_list = list(unique_position)

    return jsonify(position_list)


def calculate_age(dob_str):
    try:
        if dob_str:
            # Parse the date using dateutil.parser
            dob = parser.parse(dob_str)
            today = datetime.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            return age
        else:
            return 'No Date of Birth'
    except ValueError:
        return 'Invalid Date'


if __name__ == '__main__':
    app.run(debug=True)

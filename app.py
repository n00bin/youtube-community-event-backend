import calendar
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request
from db import db
from state import set_suggestions_open, set_poll_open, suggestionsOpen, pollOpen
import atexit
from flask_migrate import Migrate
from models import PollSuggestion, Winner, Suggestion
from routes import setup_routes, main_routes
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS  # Import CORS
from models import db  # Your database setup

app = Flask(__name__)  # The app object must be defined first

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///suggestions.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Set the secret key for the application (use a secure random value)
app.secret_key = "n00bin"

# Enable CORS with credentials
from flask_cors import CORS

CORS(app, supports_credentials=True, resources={
    r"/*": {"origins": "https://youtube-frontend-one-sigma.vercel.app"}
})

# Add CORS logging
@app.after_request
def log_cors(response):
    print(f"Origin: {request.headers.get('Origin')}")
    print(f"Access-Control-Allow-Origin: {response.headers.get('Access-Control-Allow-Origin')}")
    return response

# Initialize the database
db.init_app(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# Initialize LoginManager
from flask_login import LoginManager
from models import User  # Import your User model

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# User loader function
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))  # Adjust according to your User model

# Import and set up routes
setup_routes(app)

# Register the main_routes blueprint
app.register_blueprint(main_routes)

# Initialize Scheduler
scheduler = BackgroundScheduler()


# Task 1: Open Suggestions at the Start of the Month
def open_suggestions():
    """Open suggestions for the new month."""
    try:
        now = datetime.now()
        _, last_day = calendar.monthrange(now.year, now.month)
        end_of_month = datetime(now.year, now.month, last_day, 23, 59, 59)
        suggestions_close_date = end_of_month - timedelta(days=7)

        set_suggestions_open(True)
        set_poll_open(False)

        print(f"Suggestions opened. State: suggestionsOpen={suggestionsOpen}, pollOpen={pollOpen}.")
        print(f"Suggestions will close on {suggestions_close_date}.")

        # Dynamically schedule the closing of suggestions
        scheduler.add_job(close_suggestions, 'date', run_date=suggestions_close_date, id="close_suggestions_task", replace_existing=True)
    except Exception as e:
        print(f"Error opening suggestions: {e}")

# Task 2: Close Suggestions and Generate Poll
def close_suggestions():
    """Close suggestions and generate poll."""
    try:
        now = datetime.now()
        poll_close_date = now + timedelta(days=7)

        set_suggestions_open(False)
        set_poll_open(True)

        print(f"Suggestions closed. Poll opened. State: suggestionsOpen={suggestionsOpen}, pollOpen={pollOpen}.")
        print(f"Poll will close on {poll_close_date}.")

        with app.app_context():
            # Clear old poll data
            PollSuggestion.query.delete()
            db.session.commit()

            # Fetch the top 3 suggestions by votes
            top_suggestions = Suggestion.query.order_by(Suggestion.votes.desc()).limit(3).all()

            # Save these suggestions as poll entries
            for suggestion in top_suggestions:
                poll_suggestion = PollSuggestion(
                    suggestion_id=suggestion.id,
                    title=suggestion.title,
                    votes=0
                )
                db.session.add(poll_suggestion)

            db.session.commit()
            print("Poll generated and saved to the database.")

        # Dynamically schedule poll closure
        scheduler.add_job(close_poll, 'date', run_date=poll_close_date, id="close_poll_task", replace_existing=True)
    except Exception as e:
        print(f"Error closing suggestions: {e}")

# Task 3: Close Poll
def close_poll():
    """Close the current poll and save the winning game."""
    try:
        with app.app_context():
            winner = PollSuggestion.query.order_by(PollSuggestion.votes.desc()).first()

            if winner:
                # Check if the game is already in the Winners table
                existing_winner = Winner.query.filter_by(title=winner.title).first()
                if not existing_winner:
                    new_winner = Winner(title=winner.title)
                    db.session.add(new_winner)
                    db.session.commit()
                    print(f"Winner '{winner.title}' saved to the Winners table.")
                else:
                    print(f"Winner '{winner.title}' is already in the Winners table.")
            else:
                print("No winner to save.")
    except Exception as e:
        print(f"Error closing poll: {e}")

# Task 4: Clear Votes and Suggestions
def clear_votes_and_suggestions():
    """Clear votes and suggestions for the new month."""
    try:
        with app.app_context():
            Suggestion.query.delete()
            PollSuggestion.query.delete()
            db.session.commit()
            print(f"All suggestions and polls cleared at {datetime.now()}.")
    except Exception as e:
        print(f"Error during cleanup: {e}")

scheduler.add_job(open_suggestions, 'cron', day=1, hour=0, minute=0)
print("Scheduled: open_suggestions to run at midnight on the 1st of every month.")

scheduler.add_job(clear_votes_and_suggestions, 'cron', day=1, hour=0, minute=0)
print("Scheduled: clear_votes_and_suggestions to run at midnight on the 1st of every month.")

# Dynamically Schedule Closing Suggestions for the Current Month
def schedule_close_suggestions():
    """Schedule suggestions closure dynamically 7 days before the end of the month."""
    try:
        now = datetime.now()
        _, last_day = calendar.monthrange(now.year, now.month)
        close_date = datetime(now.year, now.month, last_day, 23, 59, 59) - timedelta(days=7)
        print(f"Scheduled close_suggestions for {close_date}.")
        scheduler.add_job(close_suggestions, 'date', run_date=close_date, id="close_suggestions_task", replace_existing=True)
    except Exception as e:
        print(f"Error scheduling close_suggestions: {e}")

schedule_close_suggestions()

# Start the scheduler
scheduler.start()

# Ensure the scheduler shuts down properly when the app exits
atexit.register(lambda: scheduler.shutdown())

if __name__ == "__main__":
    app.run(debug=True)

from flask import Blueprint, request, jsonify, session
from state import set_suggestions_open, set_poll_open, suggestionsOpen, pollOpen
from models import Suggestion, db, PollSuggestion, User
from utils import error_response
from werkzeug.security import check_password_hash
from flask_login import login_required, current_user, login_user

# Define the blueprint for routes
main_routes = Blueprint('main_routes', __name__)

@main_routes.route('/')
def index():
    return jsonify({"message": "Welcome to the YouTube Community Event App!"})

def setup_routes(app):
    @app.route('/state', methods=['GET'])
    def fetch_state():  # Renamed from get_state
        from state import suggestionsOpen, pollOpen
        return jsonify({
            "suggestionsOpen": suggestionsOpen,
            "pollOpen": pollOpen
        })

    @app.route('/state', methods=['POST'])
    def set_state():
        """Manually update state (for testing)."""
        data = request.json
        if 'suggestionsOpen' in data:
            set_suggestions_open(data['suggestionsOpen'])
        if 'pollOpen' in data:
            set_poll_open(data['pollOpen'])
        return jsonify({
            "message": "State updated",
            "suggestionsOpen": suggestionsOpen,
            "pollOpen": pollOpen
        })

    @app.route('/suggestions', methods=['POST'])
    def add_suggestion():
        if not suggestionsOpen:
            return error_response("Suggestions are currently closed.", 403)

        try:
            data = request.json
            if not data or not data.get('title'):
                return error_response("Title is required.", 400)

            if len(data['title']) > 100:
                return error_response("Title must be 100 characters or fewer.", 400)

            existing_suggestion = Suggestion.query.filter(Suggestion.title.ilike(data['title'])).first()
            if existing_suggestion:
                return error_response("This game has already been suggested.", 409)

            suggestion = Suggestion(title=data['title'])
            db.session.add(suggestion)
            db.session.commit()

            return jsonify({"message": "Suggestion added successfully.", "id": suggestion.id}), 201

        except Exception:
            return error_response("An unexpected error occurred. Please try again later.", 500)

    @app.route('/suggestions', methods=['GET'])
    def get_suggestions():
        try:
            suggestions = Suggestion.query.order_by(Suggestion.votes.desc()).all()
            return jsonify([
                {"id": s.id, "title": s.title, "votes": s.votes, "created_at": s.created_at.isoformat()}
                for s in suggestions
            ])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/suggestions/<int:suggestion_id>/upvote', methods=['POST'])
    def upvote_suggestion(suggestion_id):
        try:
            if not suggestionsOpen:
                return error_response("Upvoting is not allowed while suggestions are closed.", 403)

            suggestion = Suggestion.query.get(suggestion_id)
            if not suggestion:
                return error_response("Suggestion not found.", 404)

            # Increment the votes
            suggestion.votes += 1
            db.session.commit()

            return jsonify({"message": "Suggestion upvoted successfully.", "votes": suggestion.votes}), 200

        except Exception:
            return error_response("An unexpected error occurred while upvoting. Please try again later.", 500)

    @app.route('/poll', methods=['GET'])
    def get_poll():
        """Fetch the current poll from PollSuggestion table."""
        try:
            # Fetch all poll suggestions from PollSuggestion table
            poll_suggestions = PollSuggestion.query.all()

            # Return the poll suggestions in a structured format
            return jsonify([
                {
                    "id": p.id,  # Use Poll ID from PollSuggestion table
                    "title": p.title,  # Title of the poll entry
                    "votes": p.votes  # Current vote count
                }
                for p in poll_suggestions
            ])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/state', methods=['GET'])
    def get_state():
        return jsonify({
            "suggestionsOpen": suggestionsOpen,
            "pollOpen": pollOpen,
        })

    @app.route('/close_suggestions', methods=['POST'])
    def close_suggestions():
        """Close suggestions and generate the poll."""
        try:
            if suggestionsOpen:
                # Debug: Print current state
                print("Closing suggestions and opening poll...")

                # Close suggestions
                set_suggestions_open(False)
                set_poll_open(True)

                # Fetch top 3 suggestions
                top_suggestions = Suggestion.query.order_by(Suggestion.votes.desc()).limit(3).all()
                print(f"Top suggestions fetched: {[(s.id, s.title, s.votes) for s in top_suggestions]}")

                # Clear old poll data
                PollSuggestion.query.delete()
                db.session.commit()
                print("Old poll data cleared.")

                # Add the top 3 suggestions to the poll
                for suggestion in top_suggestions:
                    poll_suggestion = PollSuggestion(
                        suggestion_id=suggestion.id,
                        title=suggestion.title,
                        votes=0  # Poll starts with 0 votes
                    )
                    db.session.add(poll_suggestion)
                    print(f"Added to PollSuggestion: {poll_suggestion.title}")

                db.session.commit()
                print("New poll data committed.")
                return jsonify({"message": "Suggestions closed and poll created"}), 200
            else:
                return jsonify({"error": "Suggestions are already closed"}), 400
        except Exception as e:
            print(f"Error in close_suggestions: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/poll/<int:poll_suggestion_id>/vote', methods=['POST'])
    def vote_poll(poll_suggestion_id):
        try:
            if not pollOpen:
                return error_response("Poll voting is not allowed while the poll is closed.", 403)

            poll_suggestion = PollSuggestion.query.get(poll_suggestion_id)
            if not poll_suggestion:
                return error_response("Poll suggestion not found.", 404)

            # Increment the votes for the poll suggestion
            poll_suggestion.votes += 1
            db.session.commit()

            return jsonify({
                "message": "Poll vote recorded successfully.",
                "votes": poll_suggestion.votes
            }), 200

        except Exception:
            return error_response("An unexpected error occurred while voting. Please try again later.", 500)

    @main_routes.route('/', endpoint='main_index')
    def index():
        return "Welcome to the YouTube Community Event App!"

    @app.route('/scheduler_jobs', methods=['GET'])
    def list_scheduled_jobs():
        """List all active scheduled jobs."""
        from app import scheduler  # Import the scheduler from your app.py
        jobs = scheduler.get_jobs()
        return jsonify([
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
            for job in jobs
        ])

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'GET':
            return jsonify({"message": "Login endpoint for admin dashboard"})

        if request.method == 'POST':
            data = request.json
            username = data.get("username")
            password = data.get("password")

            user = User.query.filter_by(username=username).first()
            if not user or not check_password_hash(user.password, password):
                return jsonify({"message": "Invalid username or password"}), 401

            login_user(user)

            # Check if user is an admin
            if user.is_admin:
                session['admin'] = True
                return jsonify({"message": "Login successful"}), 200
            else:
                return jsonify({"message": "Unauthorized"}), 403

    @main_routes.route('/admin', methods=['GET'])
    @login_required
    def admin_dashboard():
        """Admin-only route."""
        if not session.get('admin'):  # Ensure session has the admin flag
            return jsonify({"message": "Unauthorized"}), 403

        # Return admin-specific data
        return jsonify({"message": "Welcome to the admin dashboard!"})

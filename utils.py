from flask import jsonify
from models import Suggestion, PollSuggestion, db



def error_response(message, status_code=400):
    return jsonify({"error": message}), status_code

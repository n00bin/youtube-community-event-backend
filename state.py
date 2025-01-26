# Master state
suggestionsOpen = True
pollOpen = False


def set_suggestions_open(value):
    global suggestionsOpen
    suggestionsOpen = value
    print(f"suggestionsOpen set to {suggestionsOpen}")

def set_poll_open(value):
    global pollOpen
    pollOpen = value
    print(f"pollOpen set to {pollOpen}")
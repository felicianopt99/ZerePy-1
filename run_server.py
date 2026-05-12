from src.server import start_server

if __name__ == "__main__":
    print("Starting ZerePy Web Server on http://localhost:8000")
    start_server(host="0.0.0.0", port=8000)

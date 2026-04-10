from app import create_app
from app.config import Config

Config.validate()
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
